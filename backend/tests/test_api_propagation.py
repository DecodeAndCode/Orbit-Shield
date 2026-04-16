"""Tests for POST /api/propagate endpoint."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

import numpy as np
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_propagate_returns_positions(db_session):
    """Mock SGP4 engine and verify API returns position array."""
    from src.db.session import get_session

    async def override():
        yield db_session

    app.dependency_overrides[get_session] = override

    mock_result = MagicMock()
    mock_result.positions = np.array([[[6778.0, 0.0, 0.0], [6778.0, 100.0, 0.0]]])
    mock_result.velocities = np.array([[[0.0, 7.5, 0.0], [0.0, 7.5, 0.0]]])
    mock_result.times = [
        datetime(2026, 4, 15, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 4, 15, 0, 1, tzinfo=timezone.utc),
    ]
    mock_result.norad_ids = [25544]
    mock_result.valid_mask = np.array([True])

    mock_entry = MagicMock()
    mock_entry.norad_id = 25544

    with patch("src.api.routes.propagation.propagate_catalog", return_value=mock_result):
        with patch(
            "src.api.routes.propagation.load_catalog", return_value=[mock_entry]
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/propagate",
                    json={
                        "norad_ids": [25544],
                        "duration_hours": 0.03,
                        "step_minutes": 1.0,
                    },
                )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["norad_id"] == 25544
    assert len(data[0]["positions"]) == 2
    pos = data[0]["positions"][0]
    assert "lat_deg" in pos
    assert "lon_deg" in pos
    assert "alt_km" in pos
    assert "x_km" in pos
    assert "epoch" in pos
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_propagate_empty_norad_ids(db_session):
    """Request with empty norad_ids should return 422 validation error."""
    from src.db.session import get_session

    async def override():
        yield db_session

    app.dependency_overrides[get_session] = override

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/propagate",
            json={
                "norad_ids": [],
                "duration_hours": 1.0,
                "step_minutes": 1.0,
            },
        )

    assert resp.status_code == 422  # validation error: min_length=1
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_propagate_filters_by_norad_id(db_session):
    """Only satellites matching requested norad_ids are propagated."""
    from src.db.session import get_session

    async def override():
        yield db_session

    app.dependency_overrides[get_session] = override

    # Catalog has two entries; only one is requested
    entry_a = MagicMock()
    entry_a.norad_id = 25544
    entry_b = MagicMock()
    entry_b.norad_id = 99999

    mock_result = MagicMock()
    mock_result.positions = np.array([[[6778.0, 0.0, 0.0]]])
    mock_result.velocities = np.array([[[0.0, 7.5, 0.0]]])
    mock_result.times = [datetime(2026, 4, 15, 0, 0, tzinfo=timezone.utc)]
    mock_result.norad_ids = [25544]
    mock_result.valid_mask = np.array([True])

    captured_catalog = []

    def fake_propagate(catalog, start, end, step_seconds):
        captured_catalog.extend(catalog)
        return mock_result

    with patch(
        "src.api.routes.propagation.load_catalog", return_value=[entry_a, entry_b]
    ):
        with patch(
            "src.api.routes.propagation.propagate_catalog", side_effect=fake_propagate
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/propagate",
                    json={
                        "norad_ids": [25544],
                        "duration_hours": 0.03,
                        "step_minutes": 1.0,
                    },
                )

    assert resp.status_code == 200
    # Only one entry should have been passed to propagate_catalog
    assert len(captured_catalog) == 1
    assert captured_catalog[0].norad_id == 25544
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_propagate_no_catalog_returns_empty(db_session):
    """Empty catalog (no TLEs in DB) returns empty list, not an error."""
    from src.db.session import get_session

    async def override():
        yield db_session

    app.dependency_overrides[get_session] = override

    with patch("src.api.routes.propagation.load_catalog", return_value=[]):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/propagate",
                json={
                    "norad_ids": [25544],
                    "duration_hours": 1.0,
                    "step_minutes": 1.0,
                },
            )

    assert resp.status_code == 200
    assert resp.json() == []
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_propagate_invalid_satellite_masked_out(db_session):
    """Satellites with SGP4 errors (valid_mask=False) are excluded from response."""
    from src.db.session import get_session

    async def override():
        yield db_session

    app.dependency_overrides[get_session] = override

    mock_result = MagicMock()
    mock_result.positions = np.array([
        [[6778.0, 0.0, 0.0]],
        [[0.0, 0.0, 0.0]],  # invalid satellite, will be masked
    ])
    mock_result.velocities = np.zeros((2, 1, 3))
    mock_result.times = [datetime(2026, 4, 15, 0, 0, tzinfo=timezone.utc)]
    mock_result.norad_ids = [25544, 11111]
    mock_result.valid_mask = np.array([True, False])

    entry_a = MagicMock()
    entry_a.norad_id = 25544
    entry_b = MagicMock()
    entry_b.norad_id = 11111

    with patch(
        "src.api.routes.propagation.load_catalog", return_value=[entry_a, entry_b]
    ):
        with patch(
            "src.api.routes.propagation.propagate_catalog", return_value=mock_result
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/propagate",
                    json={
                        "norad_ids": [25544, 11111],
                        "duration_hours": 0.03,
                        "step_minutes": 1.0,
                    },
                )

    assert resp.status_code == 200
    data = resp.json()
    # Only the valid satellite should appear
    assert len(data) == 1
    assert data[0]["norad_id"] == 25544
    app.dependency_overrides.clear()
