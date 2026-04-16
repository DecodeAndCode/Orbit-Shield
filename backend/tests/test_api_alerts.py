"""Tests for CRUD /api/alerts."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_create_alert(db_session):
    from src.db.session import get_session
    async def override():
        yield db_session
    app.dependency_overrides[get_session] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/alerts", json={
            "pc_threshold": 1e-4,
            "notification_channels": {"email": "test@example.com"},
            "enabled": True,
        })
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] is not None
    assert data["pc_threshold"] == 1e-4
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_alerts(db_session):
    from src.db.session import get_session
    async def override():
        yield db_session
    app.dependency_overrides[get_session] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/alerts", json={
            "pc_threshold": 1e-5,
            "enabled": True,
        })
        resp = await client.get("/api/alerts")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_alert(db_session):
    from src.db.session import get_session
    async def override():
        yield db_session
    app.dependency_overrides[get_session] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post("/api/alerts", json={"pc_threshold": 1e-4})
        alert_id = create_resp.json()["id"]
        resp = await client.put(f"/api/alerts/{alert_id}", json={
            "pc_threshold": 1e-5,
            "enabled": False,
        })
    assert resp.status_code == 200
    assert resp.json()["pc_threshold"] == 1e-5
    assert resp.json()["enabled"] is False
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_alert(db_session):
    from src.db.session import get_session
    async def override():
        yield db_session
    app.dependency_overrides[get_session] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post("/api/alerts", json={"pc_threshold": 1e-4})
        alert_id = create_resp.json()["id"]
        resp = await client.delete(f"/api/alerts/{alert_id}")
    assert resp.status_code == 204
    app.dependency_overrides.clear()
