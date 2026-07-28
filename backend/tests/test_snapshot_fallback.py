"""Tests for the offline snapshot fallback.

The contract being pinned:

  * When the database cannot be reached, read endpoints serve the bundled
    snapshot instead of failing, and say so via a response header.
  * When the database is reachable, the snapshot is never consulted.
  * Failures that are not connectivity problems keep surfacing as errors,
    so real bugs are not hidden behind stale data.
"""

from __future__ import annotations

from datetime import datetime, timezone

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

    def test_provider_capacity_block_is_connectivity(self):
        """Regression: the driver raises this during connection setup.

        asyncpg surfaces a provider capacity block as a plain Postgres error
        before SQLAlchemy wraps anything, so it is not an OperationalError and
        matching on type alone missed it — the API returned 500 instead of
        falling back.
        """

        class InternalServerError(Exception):
            """Shaped like asyncpg.exceptions.InternalServerError."""

        exc = InternalServerError(
            "Your project has exceeded the data transfer quota. "
            "Upgrade your plan to increase limits."
        )
        assert snapshot.is_connectivity_error(exc)

    def test_capacity_block_detected_through_a_cause_chain(self):
        """The driver error is usually wrapped by the time a route sees it."""
        root = Exception("Your project has exceeded the data transfer quota.")
        wrapper = RuntimeError("connection failed")
        wrapper.__cause__ = root
        assert snapshot.is_connectivity_error(wrapper)

    def test_paused_project_is_connectivity(self):
        assert snapshot.is_connectivity_error(Exception("project is paused"))

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

    async def test_propagate_served_from_snapshot(self, offline_client):
        """The globe draws conjunction geometry from this endpoint.

        Regression: without a fallback here the conjunction list rendered but
        the overlays on the globe silently disappeared.
        """
        row = snapshot.conjunctions()[0]
        ids = [row["primary_norad_id"], row["secondary_norad_id"]]
        async with offline_client as client:
            resp = await client.post(
                "/api/propagate",
                json={"norad_ids": ids, "duration_hours": 2, "step_minutes": 1},
            )
        assert resp.status_code == 200
        assert resp.headers.get(snapshot.SOURCE_HEADER) == snapshot.SOURCE_SNAPSHOT
        body = resp.json()
        assert len(body) == 2, "both conjunction partners must propagate"
        assert body[0]["positions"], "no position samples returned"

    async def test_ml_compare_served_from_snapshot(self, offline_client):
        row = snapshot.conjunctions()[0]
        async with offline_client as client:
            resp = await client.get(f"/api/ml/compare/{row['id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["conjunction_id"] == row["id"]
        assert body["pc_ml"] is not None

    async def test_satellite_search_served_from_snapshot(self, offline_client):
        name = snapshot.satellites()[0]["name"]
        async with offline_client as client:
            resp = await client.get(f"/api/satellites?search={name}")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_satellite_search_by_norad_id(self, offline_client):
        norad = snapshot.satellites()[0]["norad_id"]
        async with offline_client as client:
            resp = await client.get(f"/api/satellites?search={norad}")
        assert resp.json()["items"][0]["norad_id"] == norad

    async def test_expired_cache_is_flagged(self, offline_client, monkeypatch):
        """A cache whose events have all passed must say so.

        Conjunctions are stored with absolute times, so the whole set ages out
        once its screening window passes. An empty list would otherwise be
        indistinguishable from "your filters matched nothing".
        """
        from datetime import timedelta

        from src.api.routes import conjunctions as route

        stale = datetime.now(timezone.utc) - timedelta(days=2)
        monkeypatch.setattr(
            route.snapshot,
            "conjunctions",
            lambda: [
                {
                    "id": 1,
                    "primary_norad_id": 1,
                    "secondary_norad_id": 2,
                    "tca": stale.isoformat(),
                    "miss_distance_km": 1.0,
                    "relative_velocity_kms": 10.0,
                    "pc_classical": 1e-4,
                    "pc_ml": 0.5,
                    "screening_source": "COMPUTED",
                    "created_at": stale.isoformat(),
                }
            ],
        )
        async with offline_client as client:
            resp = await client.get("/api/conjunctions")
        assert resp.status_code == 200
        assert resp.json() == []
        assert resp.headers.get("X-Data-Expired") == "true"

    async def test_current_cache_is_not_flagged_expired(self, offline_client):
        """The real bundled snapshot must not be reported as expired."""
        async with offline_client as client:
            resp = await client.get("/api/conjunctions")
        assert resp.headers.get("X-Data-Expired") != "true", (
            "bundled snapshot has aged out — regenerate it with "
            "scripts/build_snapshot.py"
        )
