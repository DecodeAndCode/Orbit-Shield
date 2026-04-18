"""Notification dispatchers (email, slack, discord). Stubs log + try webhook."""

from __future__ import annotations

import json
import logging
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
        f"COLLIDER ALERT — Pc={pc_str} (>= {cfg.pc_threshold:.0e})\n"
        f"  {c.primary_norad_id} vs {c.secondary_norad_id}\n"
        f"  TCA: {c.tca.isoformat()}\n"
        f"  Miss: {md}"
    )


def _email(target: str, c: Conjunction, cfg: AlertConfig) -> None:
    msg = _format(c, cfg)
    smtp = getattr(settings, "smtp_url", None)
    if not smtp:
        logger.info("[email stub -> %s]\n%s", target, msg)
        return
    # Real SMTP integration deferred. Stub logs.
    logger.info("[email -> %s] %s", target, msg)


def _slack(target: str, c: Conjunction, cfg: AlertConfig) -> None:
    msg = _format(c, cfg)
    if not target.startswith("http"):
        logger.info("[slack stub channel=%s]\n%s", target, msg)
        return
    payload = {"text": msg}
    try:
        httpx.post(target, json=payload, timeout=5.0)
    except Exception:
        logger.exception("slack webhook failed")


def _discord(target: str, c: Conjunction, cfg: AlertConfig) -> None:
    msg = _format(c, cfg)
    if not target.startswith("http"):
        logger.info("[discord stub channel=%s]\n%s", target, msg)
        return
    try:
        httpx.post(target, json={"content": msg}, timeout=5.0)
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
