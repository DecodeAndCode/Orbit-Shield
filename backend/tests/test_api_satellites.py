"""Tests for GET /api/satellites endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.db.models import Satellite, OrbitalElement
from src.main import app


@pytest.fixture
async def seed_satellites(db_session):
    """Seed test satellites with orbital elements."""
    sat1 = Satellite(norad_id=25544, name="ISS", object_type="PAYLOAD", country="ISS")
    sat2 = Satellite(norad_id=48274, name="STARLINK-2305", object_type="PAYLOAD", country="US")
    db_session.add_all([sat1, sat2])
    await db_session.flush()

    from datetime import datetime, timezone
    oe1 = OrbitalElement(
        norad_id=25544, epoch=datetime(2026, 4, 1, tzinfo=timezone.utc),
        mean_motion=15.5, eccentricity=0.0001, inclination=51.6,
        tle_line1="fake", tle_line2="fake",
    )
    oe2 = OrbitalElement(
        norad_id=48274, epoch=datetime(2026, 4, 1, tzinfo=timezone.utc),
        mean_motion=15.06, eccentricity=0.0001, inclination=53.0,
        tle_line1="fake", tle_line2="fake",
    )
    db_session.add_all([oe1, oe2])
    await db_session.commit()


@pytest.mark.asyncio
async def test_list_satellites(db_session, seed_satellites):
    async def override_get_session():
        yield db_session

    from src.db.session import get_session
    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/satellites")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_search_satellites(db_session, seed_satellites):
    async def override_get_session():
        yield db_session

    from src.db.session import get_session
    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/satellites", params={"search": "ISS"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["norad_id"] == 25544
    app.dependency_overrides.clear()
