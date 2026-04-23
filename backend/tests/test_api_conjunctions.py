"""Tests for conjunctions API endpoints."""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from src.db.models import CDMHistory, Conjunction, Satellite
from src.main import app


@pytest.fixture
async def seed_conjunctions(db_session):
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
        screening_source="orbit-shield",
    )
    db_session.add(conj)
    await db_session.flush()

    cdm = CDMHistory(
        conjunction_id=conj.id,
        cdm_timestamp=datetime.now(timezone.utc),
        tca=tca,
        miss_distance_km=0.5,
        pc=2.5e-5,
    )
    db_session.add(cdm)
    await db_session.commit()
    return conj


@pytest.mark.asyncio
async def test_list_conjunctions(db_session, seed_conjunctions):
    from src.db.session import get_session

    async def override():
        yield db_session

    app.dependency_overrides[get_session] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/conjunctions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["primary_name"] == "ISS"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_conjunction_detail(db_session, seed_conjunctions):
    conj = seed_conjunctions
    from src.db.session import get_session

    async def override():
        yield db_session

    app.dependency_overrides[get_session] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/conjunctions/{conj.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == conj.id
    assert len(data["cdm_history"]) == 1
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_conjunction_not_found(db_session):
    from src.db.session import get_session

    async def override():
        yield db_session

    app.dependency_overrides[get_session] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/conjunctions/99999")
    assert resp.status_code == 404
    app.dependency_overrides.clear()
