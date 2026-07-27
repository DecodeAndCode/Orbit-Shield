"""Tests for the offline snapshot fallback.

The contract being pinned:

  * When the database cannot be reached, read endpoints serve the bundled
    snapshot instead of failing, and say so via a response header.
  * When the database is reachable, the snapshot is never consulted.
  * Failures that are not connectivity problems keep surfacing as errors,
    so real bugs are not hidden behind stale data.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError, ProgrammingError

from src.db import snapshot


class TestConnectivityClassification:
    """Only genuine unreachability may trigger the fallback."""

    def test_operational_error_is_connectivity(self):
        exc = OperationalError("SELECT 1", {}, Exception("server closed connection"))
        assert snapshot.is_connectivity_error(exc)

    def test_os_level_errors_are_connectivity(self):
        assert snapshot.is_connectivity_error(ConnectionError("refused"))
        assert snapshot.is_connectivity_error(TimeoutError("timed out"))

    @pytest.mark.parametrize(
        "exc",
        [
            ProgrammingError("SELECT bad", {}, Exception('column "x" does not exist')),
            ValueError("bad input"),
            KeyError("missing"),
            TypeError("wrong type"),
        ],
    )
    def test_application_errors_are_not_connectivity(self, exc):
        assert not snapshot.is_connectivity_error(exc), (
            f"{type(exc).__name__} would wrongly fall back to stale data"
        )


class TestSnapshotContents:
    """The bundled file must be usable, or the fallback is worthless."""

    def test_snapshot_is_available(self):
        assert snapshot.available(), "no snapshot bundled; run scripts/build_snapshot.py"

    def test_reports_generation_time(self):
        assert snapshot.generated_at()

    def test_catalog_builds_propagatable_entries(self):
        catalog = snapshot.catalog()
        assert len(catalog) > 1000, "snapshot catalog is implausibly small"
        entry = catalog[0]
        assert entry.norad_id > 0
        assert entry.satrec is not None
        assert entry.perigee_alt_km is not None

    def test_catalog_entries_propagate_with_sgp4(self):
        """Positions come from live propagation, so the Satrecs must work."""
        from datetime import datetime, timezone

        import numpy as np
        from sgp4.api import SatrecArray

        from src.propagation.sgp4_engine import datetime_to_jd

        catalog = snapshot.catalog()[:200]
        jd, fr = datetime_to_jd(datetime.now(tz=timezone.utc))
        errors, positions, _ = SatrecArray([e.satrec for e in catalog]).sgp4(
            np.array([jd]), np.array([fr])
        )
        ok = int((errors[:, 0] == 0).sum())
        assert ok > len(catalog) * 0.8, f"only {ok}/{len(catalog)} propagated"
        assert np.isfinite(positions[errors[:, 0] == 0]).all()

    def test_conjunctions_carry_ml_predictions(self):
        rows = snapshot.conjunctions()
        assert rows, "snapshot has no conjunctions"
        with_ml = [r for r in rows if r.get("pc_ml") is not None]
        assert with_ml, "snapshot conjunctions carry no ML predictions"

    def test_conjunctions_are_ordered_by_descending_risk(self):
        pcs = [r["pc_classical"] or 0 for r in snapshot.conjunctions()]
        assert pcs == sorted(pcs, reverse=True)

    def test_satellite_names_resolve(self):
        rows = snapshot.conjunctions()
        named = [
            r for r in rows[:50] if snapshot.satellite_name(r["primary_norad_id"])
        ]
        assert named, "no conjunction primaries resolve to a satellite name"


class _UnreachableSession:
    """Session stand-in that fails the way an unreachable database does.

    Overriding the dependency rather than the environment keeps the test
    deterministic: the settings object is a module-level singleton, so
    changing DATABASE_URL after import has no effect.
    """

    def _boom(self) -> OperationalError:
        return OperationalError(
            "SELECT 1", {}, Exception("connection to server failed: timeout expired")
        )

    async def execute(self, *_args, **_kwargs):
        raise self._boom()

    async def run_sync(self, *_args, **_kwargs):
        raise self._boom()


@pytest.fixture
def offline_client():
    """AsyncClient wired to the app with the database made unreachable."""
    from httpx import ASGITransport, AsyncClient

    from src.db.session import get_session
    from src.main import app

    async def _override():
        yield _UnreachableSession()

    app.dependency_overrides[get_session] = _override
    try:
        yield AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
class TestEndpointFallback:
    """End-to-end behaviour against an unreachable database."""

    async def test_conjunctions_served_from_snapshot(self, offline_client):
        async with offline_client as client:
            resp = await client.get("/api/conjunctions?hours_ahead=72&limit=5")
        assert resp.status_code == 200
        assert resp.headers.get(snapshot.SOURCE_HEADER) == snapshot.SOURCE_SNAPSHOT
        assert resp.headers.get("X-Data-Generated-At")
        body = resp.json()
        assert len(body) == 5
        assert body[0]["tca"]

    async def test_positions_served_from_snapshot(self, offline_client):
        async with offline_client as client:
            resp = await client.get("/api/positions")
        assert resp.status_code == 200
        assert resp.headers.get(snapshot.SOURCE_HEADER) == snapshot.SOURCE_SNAPSHOT
        body = resp.json()
        assert body["count"] > 1000
        first = body["positions"][0]
        assert -90 <= first["lat_deg"] <= 90
        assert -180 <= first["lon_deg"] <= 180
        assert first["alt_km"] > 80

    async def test_limit_is_respected_in_fallback(self, offline_client):
        async with offline_client as client:
            resp = await client.get("/api/conjunctions?limit=3")
        assert len(resp.json()) == 3

    async def test_detail_endpoint_served_from_snapshot(self, offline_client):
        known_id = snapshot.conjunctions()[0]["id"]
        async with offline_client as client:
            resp = await client.get(f"/api/conjunctions/{known_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == known_id

    async def test_unknown_detail_id_still_404s(self, offline_client):
        async with offline_client as client:
            resp = await client.get("/api/conjunctions/999999999")
        assert resp.status_code == 404

    async def test_health_is_unaffected(self, offline_client):
        async with offline_client as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
