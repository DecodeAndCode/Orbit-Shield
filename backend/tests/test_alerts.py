"""Tests for alerts evaluator + notifier stubs."""

from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects import sqlite as sqlite_dialect

from src.db.models import Base, AlertConfig, Conjunction, Satellite
from src.alerts.evaluator import matches, evaluate
from src.alerts.notifier import _format, dispatch


@pytest.fixture
def sync_session():
    # Patch BigInt/JSONB/ARRAY for SQLite (mirrors conftest)
    tc = sqlite_dialect.base.SQLiteTypeCompiler
    orig_bi, orig_jb, orig_ar = tc.visit_BIGINT, getattr(tc, "visit_JSONB", None), getattr(tc, "visit_ARRAY", None)
    tc.visit_BIGINT = lambda self, t, **kw: "INTEGER"
    tc.visit_JSONB = lambda self, t, **kw: "TEXT"
    tc.visit_ARRAY = lambda self, t, **kw: "TEXT"

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        Satellite.__table__, Conjunction.__table__, AlertConfig.__table__,
    ])
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()
    engine.dispose()

    tc.visit_BIGINT = orig_bi
    if orig_jb: tc.visit_JSONB = orig_jb
    if orig_ar: tc.visit_ARRAY = orig_ar


def _conj(pc=1e-3, ml=None, p=25544, sec=48274):
    return Conjunction(
        primary_norad_id=p, secondary_norad_id=sec,
        tca=datetime.now(timezone.utc) + timedelta(hours=2),
        miss_distance_km=0.5, relative_velocity_kms=14.0,
        pc_classical=pc, pc_ml=ml, screening_source="COMPUTED",
    )


def test_matches_threshold():
    cfg = AlertConfig(pc_threshold=1e-4, enabled=True)
    assert matches(_conj(pc=1e-3), cfg)
    assert not matches(_conj(pc=1e-6), cfg)


def test_matches_disabled():
    cfg = AlertConfig(pc_threshold=1e-4, enabled=False)
    assert not matches(_conj(pc=1e-3), cfg)


def test_matches_ml_priority():
    cfg = AlertConfig(pc_threshold=1e-4, enabled=True)
    # Classical low, ML high -> match
    assert matches(_conj(pc=1e-6, ml=1e-3), cfg)
    # Classical high, ML low -> no match (ML wins)
    assert not matches(_conj(pc=1e-3, ml=1e-6), cfg)


def test_matches_watched_filter():
    cfg = AlertConfig(pc_threshold=1e-4, enabled=True, watched_norad_ids=[99999])
    assert not matches(_conj(pc=1e-3), cfg)
    cfg2 = AlertConfig(pc_threshold=1e-4, enabled=True, watched_norad_ids=[25544])
    assert matches(_conj(pc=1e-3), cfg2)


def test_format_message():
    msg = _format(_conj(pc=2.5e-4), AlertConfig(pc_threshold=1e-4))
    assert "COLLIDER ALERT" in msg
    assert "2.50e-04" in msg
    assert "25544" in msg


def test_dispatch_unknown_channel(caplog):
    dispatch("telegram", "x", _conj(), AlertConfig(pc_threshold=1e-4))
    assert "unknown alert channel" in caplog.text


def test_dispatch_email_stub(caplog):
    import logging
    caplog.set_level(logging.INFO)
    dispatch("email", "ops@example.com", _conj(pc=1e-3), AlertConfig(pc_threshold=1e-4))
    assert "email" in caplog.text


def test_evaluate_dispatches(sync_session, caplog):
    import logging
    caplog.set_level(logging.INFO)
    sync_session.add(AlertConfig(
        pc_threshold=1e-4, enabled=True,
        notification_channels={"email": "a@b.c"},
    ))
    sync_session.commit()
    fired = evaluate(sync_session, [_conj(pc=1e-3)])
    assert fired == 1


def test_evaluate_no_configs(sync_session):
    assert evaluate(sync_session, [_conj(pc=1e-3)]) == 0
