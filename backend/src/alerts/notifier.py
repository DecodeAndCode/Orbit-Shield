"""Notification dispatchers — email (SMTP), Slack, Discord."""

from __future__ import annotations

import json
import logging
import smtplib
from email.message import EmailMessage
from typing import Callable

import httpx

from src.config import settings
from src.db.models import AlertConfig, Conjunction

logger = logging.getLogger(__name__)


def _format(c: Conjunction, cfg: AlertConfig) -> str:
    pc = c.pc_ml if c.pc_ml is not None else c.pc_classical
    pc_str = f"{pc:.2e}" if pc is not None else "N/A"
    md = f"{c.miss_distance_km:.3f} km" if c.miss_distance_km is not None else "N/A"
    return (
        f"ORBIT-SHIELD ALERT — Pc={pc_str} (>= {cfg.pc_threshold:.0e})\n"
        f"  {c.primary_norad_id} vs {c.secondary_norad_id}\n"
        f"  TCA: {c.tca.isoformat()}\n"
        f"  Miss: {md}"
    )


def _email(target: str, c: Conjunction, cfg: AlertConfig) -> None:
    """Send email via SMTP. Falls back to log if SMTP_HOST unset."""
    msg_body = _format(c, cfg)
    if not settings.smtp_host:
        logger.info("[email stub -> %s]\n%s", target, msg_body)
        return

    pc = c.pc_ml if c.pc_ml is not None else c.pc_classical
    pc_str = f"{pc:.2e}" if pc is not None else "N/A"

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = target
    msg["Subject"] = f"[Orbit-Shield] Conjunction Alert — Pc={pc_str}"
    msg.set_content(msg_body)

    try:
        if settings.smtp_use_tls:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as s:
                s.starttls()
                if settings.smtp_user:
                    s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as s:
                if settings.smtp_user:
                    s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)
        logger.info("email sent -> %s (Pc=%s)", target, pc_str)
    except Exception:
        logger.exception("SMTP send failed for %s", target)


def _slack(target: str, c: Conjunction, cfg: AlertConfig) -> None:
    """Post to Slack webhook. Uses per-alert target, falls back to global."""
    msg = _format(c, cfg)
    url = target if target.startswith("http") else settings.slack_webhook_url
    if not url:
        logger.info("[slack stub channel=%s]\n%s", target, msg)
        return
    try:
        r = httpx.post(url, json={"text": msg}, timeout=5.0)
        r.raise_for_status()
        logger.info("slack posted -> %s", target)
    except Exception:
        logger.exception("slack webhook failed")


def _discord(target: str, c: Conjunction, cfg: AlertConfig) -> None:
    """Post to Discord webhook. Uses per-alert target, falls back to global."""
    msg = _format(c, cfg)
    url = target if target.startswith("http") else settings.discord_webhook_url
    if not url:
        logger.info("[discord stub channel=%s]\n%s", target, msg)
        return
    try:
        r = httpx.post(url, json={"content": msg}, timeout=5.0)
        r.raise_for_status()
        logger.info("discord posted -> %s", target)
    except Exception:
        logger.exception("discord webhook failed")


_CHANNELS: dict[str, Callable[[str, Conjunction, AlertConfig], None]] = {
    "email": _email,
    "slack": _slack,
    "discord": _discord,
}


def dispatch(channel: str, target: str, c: Conjunction, cfg: AlertConfig) -> None:
    fn = _CHANNELS.get(channel)
    if fn is None:
        logger.warning("unknown alert channel: %s (payload=%s)", channel, json.dumps(target))
        return
    fn(target, c, cfg)
