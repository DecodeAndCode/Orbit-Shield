"""Tests for GET /api/ml/compare/{conjunction_id}."""

import pytest
from datetime import datetime, timedelta, timezone
from httpx import ASGITransport, AsyncClient

from src.db.models import Satellite, Conjunction
from src.main import app


@pytest.fixture
async def seed_conjunction_for_ml(db_session):
    sat1 = Satellite(norad_id=25544, name="ISS")
    sat2 = Satellite(norad_id=48274, name="STARLINK-2305")
    db_session.add_all([sat1, sat2])
    await db_session.flush()

    tca = datetime.now(timezone.utc) + timedelta(hours=24)
    conj = Conjunction(
        primary_norad_id=25544,
        secondary_norad_id=48274,
        tca=tca,
        miss_distance_km=0.5,
        relative_velocity_kms=7.2,
        pc_classical=2.5e-5,
        pc_ml=3.1e-5,
    )
    db_session.add(conj)
    await db_session.commit()
    return conj


@pytest.mark.asyncio
async def test_ml_compare(db_session, seed_conjunction_for_ml):
    conj = seed_conjunction_for_ml
    from src.db.session import get_session
    async def override():
        yield db_session
    app.dependency_overrides[get_session] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/ml/compare/{conj.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["conjunction_id"] == conj.id
    assert data["pc_classical"] == pytest.approx(2.5e-5)
    assert data["risk_label"] in ("low", "medium", "high")
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ml_compare_not_found(db_session):
    from src.db.session import get_session
    async def override():
        yield db_session
    app.dependency_overrides[get_session] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/ml/compare/99999")
    assert resp.status_code == 404
    app.dependency_overrides.clear()
