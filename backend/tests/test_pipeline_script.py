"""Tests for the scheduled pipeline entry point.

The behaviour under test is the distinction the scheduled run depends on:
a provider capacity block is a reason to skip quietly, while any other
database failure must still surface as a real failure.
"""

from __future__ import annotations

import pytest

from scripts.run_pipeline import PROVIDER_QUOTA_SIGNATURES, database_quota_block


class _Boom:
    """Stands in for create_engine, raising on connect()."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def connect(self):
        raise self._exc


def _patch_engine(monkeypatch, exc: Exception | None) -> None:
    import sqlalchemy

    if exc is None:
        return  # leave the real engine in place

    monkeypatch.setattr(
        sqlalchemy, "create_engine", lambda *a, **k: _Boom(exc), raising=True
    )


# Verbatim message returned by Neon once the monthly allowance is spent.
REAL_QUOTA_ERROR = (
    '(psycopg2.OperationalError) connection to server at "ep-divine-rain.'
    'aws.neon.tech" (2600:1f18::1), port 5432 failed: ERROR:  Your project '
    "has exceeded the data transfer quota. Upgrade your plan to increase limits."
)


def test_detects_real_provider_quota_message(monkeypatch):
    """The exact production message must be recognised as a capacity block."""
    _patch_engine(monkeypatch, Exception(REAL_QUOTA_ERROR))
    detected = database_quota_block()
    assert detected is not None
    assert "data transfer quota" in detected


@pytest.mark.parametrize(
    "message",
    [
        "FATAL: password authentication failed for user",
        "could not translate host name to address",
        "connection to server failed: Connection refused",
        "SSL SYSCALL error: EOF detected",
        "relation 'conjunctions' does not exist",
        "canceling statement due to statement timeout",
    ],
)
def test_ordinary_failures_are_not_masked(monkeypatch, message):
    """Anything that is not a capacity block must fail loudly, not skip."""
    _patch_engine(monkeypatch, Exception(message))
    assert database_quota_block() is None, (
        f"{message!r} was wrongly treated as a provider quota block"
    )


def test_reachable_database_reports_no_block(monkeypatch):
    """A database that answers SELECT 1 is not blocked."""
    import sqlalchemy

    class _Conn:
        def execute(self, *_a, **_k):
            return None

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    class _Engine:
        def connect(self):
            return _Conn()

    monkeypatch.setattr(sqlalchemy, "create_engine", lambda *a, **k: _Engine())
    assert database_quota_block() is None


def test_signatures_are_lowercase_for_case_insensitive_match():
    """Matching lowercases the message, so signatures must be lowercase."""
    for sig in PROVIDER_QUOTA_SIGNATURES:
        assert sig == sig.lower(), f"signature {sig!r} would never match"
