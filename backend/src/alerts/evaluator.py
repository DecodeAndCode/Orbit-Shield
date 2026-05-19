"""Alert evaluation: match conjunctions against AlertConfig rows, dispatch."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import AlertConfig, Conjunction
from src.alerts.notifier import dispatch

logger = logging.getLogger(__name__)


def matches(conj: Conjunction, cfg: AlertConfig) -> bool:
    """True if conjunction triggers config."""
    if not cfg.enabled:
        return False
    pc = conj.pc_ml if conj.pc_ml is not None else conj.pc_classical
    if pc is None or pc < cfg.pc_threshold:
        return False
    if cfg.watched_norad_ids:
        watched = set(cfg.watched_norad_ids)
        if conj.primary_norad_id not in watched and conj.secondary_norad_id not in watched:
            return False
    return True


def evaluate(session: Session, conjunctions: Iterable[Conjunction] | None = None) -> int:
    """Evaluate conjunctions vs all enabled alerts. Returns dispatch count.

    If `conjunctions` is None, pulls all conjunctions with alerted_at IS NULL.
    Marks alerted_at on each row dispatched to prevent re-firing.
    """
    cfgs = session.execute(
        select(AlertConfig).where(AlertConfig.enabled.is_(True))
    ).scalars().all()
    if not cfgs:
        return 0

    if conjunctions is None:
        conjunctions = (
            session.execute(
                select(Conjunction).where(Conjunction.alerted_at.is_(None))
            )
            .scalars()
            .all()
        )

    fired = 0
    for c in conjunctions:
        if c.alerted_at is not None:
            continue
        dispatched_any = False
        for cfg in cfgs:
            if matches(c, cfg):
                channels = cfg.notification_channels or {}
                for channel, target in channels.items():
                    try:
                        dispatch(channel, target, c, cfg)
                        fired += 1
                        dispatched_any = True
                    except Exception:
                        logger.exception("alert dispatch failed: %s -> %s", channel, target)
        if dispatched_any:
            c.alerted_at = datetime.now(timezone.utc)

    session.commit()
    return fired
