# Phase 5: API Routes + Frontend Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire Collider's backend computation layers (ingestion, SGP4, Pc, ML) to REST endpoints and a React+CesiumJS dashboard for local demo.

**Architecture:** Vertical slices — each task delivers one API route group + its frontend component. Backend uses async SQLAlchemy sessions via FastAPI dependency injection. Frontend uses React Query for server state, Zustand for UI state, Resium for CesiumJS, Recharts for charts, Tailwind for styling.

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy 2.0 async / React 19 / TypeScript / Vite 7 / Resium / Recharts / Zustand / TanStack React Query / Tailwind CSS 4

---

## File Structure

### Backend (new files under `backend/src/`)
- `api/schemas.py` — Pydantic response/request models for all endpoints
- `api/routes/satellites.py` — GET /api/satellites
- `api/routes/conjunctions.py` — GET /api/conjunctions, GET /api/conjunctions/{id}
- `api/routes/propagation.py` — POST /api/propagate
- `api/routes/ml.py` — GET /api/ml/compare/{conjunction_id}
- `api/routes/alerts.py` — CRUD /api/alerts
- `api/websocket.py` — WS /ws/conjunctions (replace stub)

### Backend tests
- `tests/test_api_satellites.py`
- `tests/test_api_conjunctions.py`
- `tests/test_api_propagation.py`
- `tests/test_api_ml.py`
- `tests/test_api_alerts.py`

### Frontend (new files under `frontend/src/`)
- `api/client.ts` — fetch wrapper + React Query setup
- `api/types.ts` — TypeScript types matching backend schemas
- `stores/colliderStore.ts` — Zustand store
- `components/Header.tsx` — top bar with search + status
- `components/ConjunctionTimeline.tsx` — left panel sorted by Pc
- `components/ConjunctionCard.tsx` — single conjunction card
- `components/GlobeView.tsx` — CesiumJS 3D globe
- `components/EventDetailPanel.tsx` — selected conjunction details
- `components/PcComparisonChart.tsx` — ML vs Classical Recharts chart
- `components/AlertConfigForm.tsx` — alert CRUD modal
- `App.tsx` — main layout (modify existing)
- `main.tsx` — add QueryClientProvider (modify existing)
- `index.css` — Tailwind base styles (modify existing)

---

## Task 1: Pydantic Schemas + FastAPI Router Skeleton

**Files:**
- Create: `backend/src/api/schemas.py`
- Modify: `backend/src/main.py`
- Modify: `backend/src/api/routes/__init__.py`

- [ ] **Step 1: Create Pydantic schemas**

```python
# backend/src/api/schemas.py
"""Pydantic schemas for API request/response validation."""

from datetime import date, datetime

from pydantic import BaseModel, Field


class SatelliteResponse(BaseModel):
    norad_id: int
    name: str | None
    object_type: str | None
    country: str | None
    launch_date: date | None
    rcs_size: str | None

    # Latest orbital summary (joined)
    inclination: float | None = None
    perigee_alt_km: float | None = None
    apogee_alt_km: float | None = None
    regime: str | None = None  # computed: LEO/MEO/GEO

    model_config = {"from_attributes": True}


class ConjunctionResponse(BaseModel):
    id: int
    primary_norad_id: int
    secondary_norad_id: int
    primary_name: str | None = None
    secondary_name: str | None = None
    tca: datetime
    miss_distance_km: float | None
    relative_velocity_kms: float | None
    pc_classical: float | None
    pc_ml: float | None
    screening_source: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CDMHistoryItem(BaseModel):
    id: int
    cdm_timestamp: datetime | None
    tca: datetime | None
    miss_distance_km: float | None
    pc: float | None

    model_config = {"from_attributes": True}


class ConjunctionDetailResponse(ConjunctionResponse):
    cdm_history: list[CDMHistoryItem] = []


class PropagateRequest(BaseModel):
    norad_ids: list[int] = Field(..., min_length=1, max_length=100)
    duration_hours: float = Field(default=2.0, gt=0, le=72)
    step_minutes: float = Field(default=1.0, gt=0, le=60)


class SatellitePosition(BaseModel):
    epoch: datetime
    x_km: float
    y_km: float
    z_km: float
    lat_deg: float
    lon_deg: float
    alt_km: float


class PropagateResponse(BaseModel):
    norad_id: int
    positions: list[SatellitePosition]


class MLCompareResponse(BaseModel):
    conjunction_id: int
    pc_classical: float | None
    pc_ml: float | None
    confidence: float | None
    risk_label: str  # "low", "medium", "high"
    feature_importances: dict[str, float] = {}


class AlertConfigBase(BaseModel):
    watched_norad_ids: list[int] | None = None
    pc_threshold: float = Field(default=1e-4, gt=0, le=1)
    notification_channels: dict | None = None
    enabled: bool = True


class AlertConfigCreate(AlertConfigBase):
    pass


class AlertConfigUpdate(AlertConfigBase):
    pass


class AlertConfigResponse(AlertConfigBase):
    id: int

    model_config = {"from_attributes": True}


class PaginatedResponse(BaseModel):
    items: list
    total: int
    limit: int
    offset: int
```

- [ ] **Step 2: Wire router into FastAPI app**

```python
# backend/src/api/routes/__init__.py
"""API route registry."""

from fastapi import APIRouter

api_router = APIRouter(prefix="/api")
```

Update `backend/src/main.py` — add after `app` definition:

```python
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import api_router

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/api/schemas.py backend/src/api/routes/__init__.py backend/src/main.py
git commit -m "feat: Pydantic schemas and FastAPI router skeleton"
```

---

## Task 2: Satellites API Route

**Files:**
- Create: `backend/src/api/routes/satellites.py`
- Modify: `backend/src/api/routes/__init__.py`
- Create: `backend/tests/test_api_satellites.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_api_satellites.py
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
    from src.db.session import get_session
    app.dependency_overrides[get_session] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/satellites")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_search_satellites(db_session, seed_satellites):
    from src.db.session import get_session
    app.dependency_overrides[get_session] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/satellites", params={"search": "ISS"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["norad_id"] == 25544
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_api_satellites.py -v`
Expected: FAIL — 404 (route not registered)

- [ ] **Step 3: Implement satellites route**

```python
# backend/src/api/routes/satellites.py
"""GET /api/satellites — paginated satellite catalog."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import SatelliteResponse
from src.db.models import OrbitalElement, Satellite
from src.db.session import get_session
from src.propagation.sgp4_engine import R_EARTH_KM, MU_EARTH

router = APIRouter()


def _compute_regime(perigee_alt_km: float | None) -> str | None:
    if perigee_alt_km is None:
        return None
    if perigee_alt_km < 2000:
        return "LEO"
    elif perigee_alt_km < 35786:
        return "MEO"
    else:
        return "GEO"


def _compute_altitudes(mean_motion: float | None, eccentricity: float | None):
    if mean_motion is None or eccentricity is None or mean_motion <= 0:
        return None, None
    import math
    period_sec = 86400.0 / mean_motion
    a_km = (MU_EARTH * (period_sec / (2 * math.pi)) ** 2) ** (1.0 / 3.0)
    perigee = a_km * (1 - eccentricity) - R_EARTH_KM
    apogee = a_km * (1 + eccentricity) - R_EARTH_KM
    return perigee, apogee


@router.get("/satellites")
async def list_satellites(
    search: str | None = Query(None),
    regime: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    # Subquery: latest orbital element per satellite
    latest_oe = (
        select(
            OrbitalElement.norad_id,
            OrbitalElement.inclination,
            OrbitalElement.mean_motion,
            OrbitalElement.eccentricity,
            func.row_number()
            .over(
                partition_by=OrbitalElement.norad_id,
                order_by=OrbitalElement.epoch.desc(),
            )
            .label("rn"),
        )
        .subquery()
    )
    latest = select(latest_oe).where(latest_oe.c.rn == 1).subquery()

    # Base query
    query = (
        select(Satellite, latest.c.inclination, latest.c.mean_motion, latest.c.eccentricity)
        .outerjoin(latest, Satellite.norad_id == latest.c.norad_id)
    )

    if search:
        query = query.where(
            Satellite.name.ilike(f"%{search}%")
            | (Satellite.norad_id == int(search) if search.isdigit() else False)
        )

    # Count total before pagination
    count_q = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_q)).scalar_one()

    # Paginate
    rows = (await session.execute(query.offset(offset).limit(limit))).all()

    items = []
    for sat, incl, mm, ecc in rows:
        perigee, apogee = _compute_altitudes(mm, ecc)
        regime_val = _compute_regime(perigee)

        items.append(SatelliteResponse(
            norad_id=sat.norad_id,
            name=sat.name,
            object_type=sat.object_type,
            country=sat.country,
            launch_date=sat.launch_date,
            rcs_size=sat.rcs_size,
            inclination=incl,
            perigee_alt_km=round(perigee, 2) if perigee else None,
            apogee_alt_km=round(apogee, 2) if apogee else None,
            regime=regime_val,
        ))

    # Filter by regime in-memory (computed field)
    if regime:
        items = [i for i in items if i.regime == regime.upper()]

    return {"items": items, "total": total, "limit": limit, "offset": offset}
```

Register in `backend/src/api/routes/__init__.py`:

```python
"""API route registry."""

from fastapi import APIRouter

from src.api.routes.satellites import router as satellites_router

api_router = APIRouter(prefix="/api")
api_router.include_router(satellites_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_api_satellites.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/routes/satellites.py backend/src/api/routes/__init__.py backend/tests/test_api_satellites.py
git commit -m "feat: GET /api/satellites with search and pagination"
```

---

## Task 3: Conjunctions API Route

**Files:**
- Create: `backend/src/api/routes/conjunctions.py`
- Modify: `backend/src/api/routes/__init__.py`
- Create: `backend/tests/test_api_conjunctions.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_api_conjunctions.py
"""Tests for conjunctions API endpoints."""

import pytest
from datetime import datetime, timedelta, timezone
from httpx import ASGITransport, AsyncClient

from src.db.models import Satellite, Conjunction, CDMHistory
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
        screening_source="collider",
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
    app.dependency_overrides[get_session] = lambda: db_session
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
    app.dependency_overrides[get_session] = lambda: db_session
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
    app.dependency_overrides[get_session] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/conjunctions/99999")
    assert resp.status_code == 404
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_api_conjunctions.py -v`
Expected: FAIL — 404/route not found

- [ ] **Step 3: Implement conjunctions routes**

```python
# backend/src/api/routes/conjunctions.py
"""Conjunctions API: list and detail endpoints."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.schemas import (
    CDMHistoryItem,
    ConjunctionDetailResponse,
    ConjunctionResponse,
)
from src.db.models import Conjunction, Satellite
from src.db.session import get_session

router = APIRouter()


@router.get("/conjunctions")
async def list_conjunctions(
    min_pc: float | None = Query(None, ge=0),
    hours_ahead: int = Query(72, ge=1, le=720),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[ConjunctionResponse]:
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=hours_ahead)

    query = (
        select(Conjunction)
        .where(Conjunction.tca >= now, Conjunction.tca <= cutoff)
        .order_by(Conjunction.pc_classical.desc().nulls_last())
        .limit(limit)
    )

    if min_pc is not None:
        query = query.where(Conjunction.pc_classical >= min_pc)

    result = await session.execute(query)
    conjunctions = result.scalars().all()

    # Batch-load satellite names
    norad_ids = set()
    for c in conjunctions:
        norad_ids.add(c.primary_norad_id)
        norad_ids.add(c.secondary_norad_id)

    names: dict[int, str | None] = {}
    if norad_ids:
        sat_q = select(Satellite.norad_id, Satellite.name).where(
            Satellite.norad_id.in_(norad_ids)
        )
        for row in (await session.execute(sat_q)).all():
            names[row[0]] = row[1]

    return [
        ConjunctionResponse(
            id=c.id,
            primary_norad_id=c.primary_norad_id,
            secondary_norad_id=c.secondary_norad_id,
            primary_name=names.get(c.primary_norad_id),
            secondary_name=names.get(c.secondary_norad_id),
            tca=c.tca,
            miss_distance_km=c.miss_distance_km,
            relative_velocity_kms=c.relative_velocity_kms,
            pc_classical=c.pc_classical,
            pc_ml=c.pc_ml,
            screening_source=c.screening_source,
            created_at=c.created_at,
        )
        for c in conjunctions
    ]


@router.get("/conjunctions/{conjunction_id}")
async def get_conjunction(
    conjunction_id: int,
    session: AsyncSession = Depends(get_session),
) -> ConjunctionDetailResponse:
    query = (
        select(Conjunction)
        .options(selectinload(Conjunction.cdm_history))
        .where(Conjunction.id == conjunction_id)
    )
    result = await session.execute(query)
    conj = result.scalar_one_or_none()

    if conj is None:
        raise HTTPException(status_code=404, detail="Conjunction not found")

    # Get satellite names
    sat_q = select(Satellite.norad_id, Satellite.name).where(
        Satellite.norad_id.in_([conj.primary_norad_id, conj.secondary_norad_id])
    )
    names = {row[0]: row[1] for row in (await session.execute(sat_q)).all()}

    return ConjunctionDetailResponse(
        id=conj.id,
        primary_norad_id=conj.primary_norad_id,
        secondary_norad_id=conj.secondary_norad_id,
        primary_name=names.get(conj.primary_norad_id),
        secondary_name=names.get(conj.secondary_norad_id),
        tca=conj.tca,
        miss_distance_km=conj.miss_distance_km,
        relative_velocity_kms=conj.relative_velocity_kms,
        pc_classical=conj.pc_classical,
        pc_ml=conj.pc_ml,
        screening_source=conj.screening_source,
        created_at=conj.created_at,
        cdm_history=[
            CDMHistoryItem(
                id=cdm.id,
                cdm_timestamp=cdm.cdm_timestamp,
                tca=cdm.tca,
                miss_distance_km=cdm.miss_distance_km,
                pc=cdm.pc,
            )
            for cdm in conj.cdm_history
        ],
    )
```

Register in `backend/src/api/routes/__init__.py` — add:

```python
from src.api.routes.conjunctions import router as conjunctions_router
api_router.include_router(conjunctions_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_api_conjunctions.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/routes/conjunctions.py backend/src/api/routes/__init__.py backend/tests/test_api_conjunctions.py
git commit -m "feat: GET /api/conjunctions list and detail endpoints"
```

---

## Task 4: Propagation API Route

**Files:**
- Create: `backend/src/api/routes/propagation.py`
- Modify: `backend/src/api/routes/__init__.py`
- Create: `backend/tests/test_api_propagation.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_api_propagation.py
"""Tests for POST /api/propagate endpoint."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from httpx import ASGITransport, AsyncClient

import numpy as np

from src.main import app


@pytest.mark.asyncio
async def test_propagate_returns_positions(db_session):
    """Mock SGP4 engine and verify API returns position array."""
    from src.db.session import get_session
    app.dependency_overrides[get_session] = lambda: db_session

    # Mock the propagation engine
    mock_result = MagicMock()
    mock_result.positions = np.array([[[6778.0, 0.0, 0.0], [6778.0, 100.0, 0.0]]])
    mock_result.velocities = np.array([[[0.0, 7.5, 0.0], [0.0, 7.5, 0.0]]])
    mock_result.times = [
        datetime(2026, 4, 15, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 4, 15, 0, 1, tzinfo=timezone.utc),
    ]
    mock_result.norad_ids = [25544]
    mock_result.valid_mask = np.array([True])

    with patch("src.api.routes.propagation.propagate_catalog", return_value=mock_result):
        with patch("src.api.routes.propagation.load_catalog", return_value=[MagicMock()]):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/api/propagate", json={
                    "norad_ids": [25544],
                    "duration_hours": 0.03,
                    "step_minutes": 1.0,
                })

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["norad_id"] == 25544
    assert len(data[0]["positions"]) == 2
    assert "lat_deg" in data[0]["positions"][0]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_propagate_empty_norad_ids(db_session):
    from src.db.session import get_session
    app.dependency_overrides[get_session] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/propagate", json={
            "norad_ids": [],
            "duration_hours": 1.0,
            "step_minutes": 1.0,
        })
    assert resp.status_code == 422  # validation error
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_api_propagation.py -v`
Expected: FAIL — 404/route not found

- [ ] **Step 3: Implement propagation route**

```python
# backend/src/api/routes/propagation.py
"""POST /api/propagate — run SGP4 propagation for selected satellites."""

import math
from datetime import datetime, timezone

import numpy as np
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import PropagateRequest, PropagateResponse, SatellitePosition
from src.db.session import get_session
from src.propagation.sgp4_engine import (
    R_EARTH_KM,
    load_catalog,
    propagate_catalog,
)

router = APIRouter()


def _teme_to_geodetic(x_km: float, y_km: float, z_km: float, epoch: datetime):
    """Convert TEME position to lat/lon/alt (simplified, ignoring Earth rotation offset)."""
    r = math.sqrt(x_km**2 + y_km**2 + z_km**2)
    lat = math.degrees(math.asin(z_km / r)) if r > 0 else 0.0
    lon = math.degrees(math.atan2(y_km, x_km))
    alt = r - R_EARTH_KM
    return lat, lon, alt


@router.post("/propagate")
async def propagate(
    req: PropagateRequest,
    session: AsyncSession = Depends(get_session),
) -> list[PropagateResponse]:
    # Load catalog entries for requested NORAD IDs
    sync_session = session.sync_session
    catalog = load_catalog(sync_session, norad_ids=req.norad_ids)

    if not catalog:
        return []

    step_seconds = int(req.step_minutes * 60)
    window_hours = req.duration_hours

    result = propagate_catalog(
        catalog,
        step_seconds=step_seconds,
        window_hours=window_hours,
    )

    responses = []
    for i, norad_id in enumerate(result.norad_ids):
        if not result.valid_mask[i]:
            continue

        positions = []
        for t_idx, epoch in enumerate(result.times):
            pos = result.positions[i, t_idx]
            lat, lon, alt = _teme_to_geodetic(pos[0], pos[1], pos[2], epoch)
            positions.append(SatellitePosition(
                epoch=epoch,
                x_km=round(float(pos[0]), 3),
                y_km=round(float(pos[1]), 3),
                z_km=round(float(pos[2]), 3),
                lat_deg=round(lat, 4),
                lon_deg=round(lon, 4),
                alt_km=round(alt, 2),
            ))

        responses.append(PropagateResponse(norad_id=norad_id, positions=positions))

    return responses
```

Register in `backend/src/api/routes/__init__.py` — add:

```python
from src.api.routes.propagation import router as propagation_router
api_router.include_router(propagation_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_api_propagation.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/routes/propagation.py backend/src/api/routes/__init__.py backend/tests/test_api_propagation.py
git commit -m "feat: POST /api/propagate with TEME to geodetic conversion"
```

---

## Task 5: ML Compare API Route

**Files:**
- Create: `backend/src/api/routes/ml.py`
- Modify: `backend/src/api/routes/__init__.py`
- Create: `backend/tests/test_api_ml.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_api_ml.py
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
    app.dependency_overrides[get_session] = lambda: db_session
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
    app.dependency_overrides[get_session] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/ml/compare/99999")
    assert resp.status_code == 404
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_api_ml.py -v`
Expected: FAIL — 404

- [ ] **Step 3: Implement ML compare route**

```python
# backend/src/api/routes/ml.py
"""GET /api/ml/compare/{conjunction_id} — classical vs ML Pc comparison."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import MLCompareResponse
from src.db.models import Conjunction
from src.db.session import get_session

router = APIRouter()


def _risk_label(pc: float | None) -> str:
    if pc is None:
        return "low"
    if pc >= 1e-4:
        return "high"
    elif pc >= 1e-6:
        return "medium"
    return "low"


@router.get("/ml/compare/{conjunction_id}")
async def ml_compare(
    conjunction_id: int,
    session: AsyncSession = Depends(get_session),
) -> MLCompareResponse:
    result = await session.execute(
        select(Conjunction).where(Conjunction.id == conjunction_id)
    )
    conj = result.scalar_one_or_none()

    if conj is None:
        raise HTTPException(status_code=404, detail="Conjunction not found")

    # Use the higher of classical/ML Pc for risk label
    effective_pc = max(
        conj.pc_classical or 0,
        conj.pc_ml or 0,
    ) or None

    # Confidence: how close ML and classical agree (1.0 = perfect match)
    confidence = None
    if conj.pc_classical and conj.pc_ml and conj.pc_classical > 0 and conj.pc_ml > 0:
        import math
        log_ratio = abs(math.log10(conj.pc_ml) - math.log10(conj.pc_classical))
        confidence = round(max(0.0, 1.0 - log_ratio / 3.0), 3)  # 3 orders of magnitude = 0

    return MLCompareResponse(
        conjunction_id=conj.id,
        pc_classical=conj.pc_classical,
        pc_ml=conj.pc_ml,
        confidence=confidence,
        risk_label=_risk_label(effective_pc),
        feature_importances={},  # populated when trained model is available
    )
```

Register in `backend/src/api/routes/__init__.py` — add:

```python
from src.api.routes.ml import router as ml_router
api_router.include_router(ml_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_api_ml.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/routes/ml.py backend/src/api/routes/__init__.py backend/tests/test_api_ml.py
git commit -m "feat: GET /api/ml/compare with classical vs ML Pc"
```

---

## Task 6: Alerts CRUD API Route

**Files:**
- Create: `backend/src/api/routes/alerts.py`
- Modify: `backend/src/api/routes/__init__.py`
- Create: `backend/tests/test_api_alerts.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_api_alerts.py
"""Tests for CRUD /api/alerts."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_create_alert(db_session):
    from src.db.session import get_session
    app.dependency_overrides[get_session] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/alerts", json={
            "watched_norad_ids": [25544],
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
    app.dependency_overrides[get_session] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create one first
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
    app.dependency_overrides[get_session] = lambda: db_session
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
    app.dependency_overrides[get_session] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post("/api/alerts", json={"pc_threshold": 1e-4})
        alert_id = create_resp.json()["id"]
        resp = await client.delete(f"/api/alerts/{alert_id}")
    assert resp.status_code == 204
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_api_alerts.py -v`
Expected: FAIL — 404

- [ ] **Step 3: Implement alerts CRUD**

```python
# backend/src/api/routes/alerts.py
"""CRUD /api/alerts — alert configuration management."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import AlertConfigCreate, AlertConfigResponse, AlertConfigUpdate
from src.db.models import AlertConfig
from src.db.session import get_session

router = APIRouter()


@router.get("/alerts")
async def list_alerts(
    session: AsyncSession = Depends(get_session),
) -> list[AlertConfigResponse]:
    result = await session.execute(select(AlertConfig))
    configs = result.scalars().all()
    return [AlertConfigResponse.model_validate(c) for c in configs]


@router.post("/alerts", status_code=201)
async def create_alert(
    body: AlertConfigCreate,
    session: AsyncSession = Depends(get_session),
) -> AlertConfigResponse:
    config = AlertConfig(
        watched_norad_ids=body.watched_norad_ids,
        pc_threshold=body.pc_threshold,
        notification_channels=body.notification_channels,
        enabled=body.enabled,
    )
    session.add(config)
    await session.flush()
    await session.refresh(config)
    return AlertConfigResponse.model_validate(config)


@router.put("/alerts/{alert_id}")
async def update_alert(
    alert_id: int,
    body: AlertConfigUpdate,
    session: AsyncSession = Depends(get_session),
) -> AlertConfigResponse:
    result = await session.execute(
        select(AlertConfig).where(AlertConfig.id == alert_id)
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="Alert config not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(config, field, value)

    await session.flush()
    await session.refresh(config)
    return AlertConfigResponse.model_validate(config)


@router.delete("/alerts/{alert_id}", status_code=204)
async def delete_alert(
    alert_id: int,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(AlertConfig).where(AlertConfig.id == alert_id)
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="Alert config not found")

    await session.delete(config)
    return Response(status_code=204)
```

Register in `backend/src/api/routes/__init__.py` — add:

```python
from src.api.routes.alerts import router as alerts_router
api_router.include_router(alerts_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_api_alerts.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/routes/alerts.py backend/src/api/routes/__init__.py backend/tests/test_api_alerts.py
git commit -m "feat: CRUD /api/alerts for alert configuration"
```

---

## Task 7: WebSocket Conjunctions Endpoint

**Files:**
- Modify: `backend/src/api/websocket.py`
- Modify: `backend/src/main.py`

- [ ] **Step 1: Implement WebSocket endpoint**

```python
# backend/src/api/websocket.py
"""WebSocket endpoint for real-time conjunction updates."""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Conjunction, Satellite
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)

# Connected clients
clients: set[WebSocket] = set()


async def _fetch_latest_conjunctions(limit: int = 10) -> list[dict]:
    """Fetch latest conjunctions from DB."""
    async with async_session_factory() as session:
        now = datetime.now(timezone.utc)
        query = (
            select(Conjunction)
            .where(Conjunction.tca >= now)
            .order_by(Conjunction.pc_classical.desc().nulls_last())
            .limit(limit)
        )
        result = await session.execute(query)
        conjunctions = result.scalars().all()

        # Load names
        norad_ids = set()
        for c in conjunctions:
            norad_ids.add(c.primary_norad_id)
            norad_ids.add(c.secondary_norad_id)

        names: dict[int, str | None] = {}
        if norad_ids:
            sat_q = select(Satellite.norad_id, Satellite.name).where(
                Satellite.norad_id.in_(norad_ids)
            )
            for row in (await session.execute(sat_q)).all():
                names[row[0]] = row[1]

        return [
            {
                "id": c.id,
                "primary_norad_id": c.primary_norad_id,
                "secondary_norad_id": c.secondary_norad_id,
                "primary_name": names.get(c.primary_norad_id),
                "secondary_name": names.get(c.secondary_norad_id),
                "tca": c.tca.isoformat(),
                "miss_distance_km": c.miss_distance_km,
                "pc_classical": c.pc_classical,
                "pc_ml": c.pc_ml,
            }
            for c in conjunctions
        ]


async def conjunction_websocket(websocket: WebSocket):
    """Handle a WebSocket connection for conjunction updates."""
    await websocket.accept()
    clients.add(websocket)
    logger.info("WebSocket client connected (%d total)", len(clients))

    try:
        # Send initial data
        latest = await _fetch_latest_conjunctions()
        await websocket.send_json({"type": "initial", "data": latest})

        # Keep alive — send updates every 30 seconds
        while True:
            await asyncio.sleep(30)
            latest = await _fetch_latest_conjunctions()
            await websocket.send_json({"type": "update", "data": latest})
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(websocket)
        logger.info("WebSocket client disconnected (%d remaining)", len(clients))


async def broadcast_conjunction_update(conjunction_data: dict):
    """Broadcast a conjunction update to all connected clients."""
    message = json.dumps({"type": "new_conjunction", "data": conjunction_data})
    disconnected = set()
    for ws in clients:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.add(ws)
    clients.difference_update(disconnected)
```

- [ ] **Step 2: Register WebSocket in main.py**

Add to `backend/src/main.py` after `app.include_router(api_router)`:

```python
from src.api.websocket import conjunction_websocket

app.websocket("/ws/conjunctions")(conjunction_websocket)
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/api/websocket.py backend/src/main.py
git commit -m "feat: WebSocket /ws/conjunctions with auto-refresh"
```

---

## Task 8: Frontend Setup — Dependencies + Tailwind + Vite Proxy

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.ts`
- Create: `frontend/.env`
- Modify: `frontend/src/index.css`
- Modify: `frontend/src/main.tsx`

- [ ] **Step 1: Install frontend dependencies**

```bash
cd frontend && npm install \
  resium cesium \
  @tanstack/react-query \
  zustand \
  recharts \
  @tailwindcss/vite tailwindcss
```

- [ ] **Step 2: Create .env with Cesium token**

```bash
# frontend/.env
VITE_CESIUM_ION_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJmNzU0NWE1ZS01NTVhLTRiOWEtYWFmYy03ZWI3NjBiMzU3MTYiLCJpZCI6NDE4Nzg1LCJpYXQiOjE3NzYyOTUwMzZ9.PUkPgVrH9i7wv9eWXVLR-Bqy_0kQU1JCcBWP2ThG-oY
```

- [ ] **Step 3: Configure Vite with Tailwind + API proxy + Cesium**

```typescript
// frontend/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { viteStaticCopy } from "vite-plugin-static-copy";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    viteStaticCopy({
      targets: [
        {
          src: "node_modules/cesium/Build/Cesium/Workers/**",
          dest: "cesium/Workers",
        },
        {
          src: "node_modules/cesium/Build/Cesium/ThirdParty/**",
          dest: "cesium/ThirdParty",
        },
        {
          src: "node_modules/cesium/Build/Cesium/Assets/**",
          dest: "cesium/Assets",
        },
        {
          src: "node_modules/cesium/Build/Cesium/Widgets/**",
          dest: "cesium/Widgets",
        },
      ],
    }),
  ],
  define: {
    CESIUM_BASE_URL: JSON.stringify("/cesium"),
  },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/ws": {
        target: "http://localhost:8000",
        ws: true,
      },
    },
  },
});
```

Also install the static copy plugin:

```bash
cd frontend && npm install -D vite-plugin-static-copy
```

- [ ] **Step 4: Set up Tailwind base styles**

```css
/* frontend/src/index.css */
@import "tailwindcss";

:root {
  --color-bg-primary: #0a0e1a;
  --color-bg-secondary: #111827;
  --color-bg-card: #1a2332;
  --color-border: #2d3748;
  --color-text-primary: #e2e8f0;
  --color-text-secondary: #94a3b8;
  --color-risk-low: #22c55e;
  --color-risk-medium: #eab308;
  --color-risk-high: #ef4444;
  --color-accent: #3b82f6;
}

body {
  margin: 0;
  background-color: var(--color-bg-primary);
  color: var(--color-text-primary);
  font-family: "Inter", system-ui, -apple-system, sans-serif;
}
```

- [ ] **Step 5: Set up main.tsx with QueryClient**

```tsx
// frontend/src/main.tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Ion } from "cesium";
import App from "./App";
import "./index.css";

Ion.defaultAccessToken = import.meta.env.VITE_CESIUM_ION_TOKEN;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchInterval: 30_000,
      staleTime: 10_000,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>
);
```

- [ ] **Step 6: Commit**

```bash
cd frontend && git add -A
git commit -m "feat: frontend setup — Tailwind, Resium, React Query, Vite proxy"
```

---

## Task 9: TypeScript Types + API Client + Zustand Store

**Files:**
- Create: `frontend/src/api/types.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/stores/colliderStore.ts`

- [ ] **Step 1: Create TypeScript types**

```typescript
// frontend/src/api/types.ts
export interface SatelliteResponse {
  norad_id: number;
  name: string | null;
  object_type: string | null;
  country: string | null;
  launch_date: string | null;
  rcs_size: string | null;
  inclination: number | null;
  perigee_alt_km: number | null;
  apogee_alt_km: number | null;
  regime: string | null;
}

export interface ConjunctionResponse {
  id: number;
  primary_norad_id: number;
  secondary_norad_id: number;
  primary_name: string | null;
  secondary_name: string | null;
  tca: string;
  miss_distance_km: number | null;
  relative_velocity_kms: number | null;
  pc_classical: number | null;
  pc_ml: number | null;
  screening_source: string | null;
  created_at: string;
}

export interface CDMHistoryItem {
  id: number;
  cdm_timestamp: string | null;
  tca: string | null;
  miss_distance_km: number | null;
  pc: number | null;
}

export interface ConjunctionDetailResponse extends ConjunctionResponse {
  cdm_history: CDMHistoryItem[];
}

export interface SatellitePosition {
  epoch: string;
  x_km: number;
  y_km: number;
  z_km: number;
  lat_deg: number;
  lon_deg: number;
  alt_km: number;
}

export interface PropagateResponse {
  norad_id: number;
  positions: SatellitePosition[];
}

export interface MLCompareResponse {
  conjunction_id: number;
  pc_classical: number | null;
  pc_ml: number | null;
  confidence: number | null;
  risk_label: "low" | "medium" | "high";
  feature_importances: Record<string, number>;
}

export interface AlertConfigResponse {
  id: number;
  watched_norad_ids: number[] | null;
  pc_threshold: number;
  notification_channels: Record<string, string> | null;
  enabled: boolean;
}

export type RiskLevel = "low" | "medium" | "high";
```

- [ ] **Step 2: Create API client with React Query hooks**

```typescript
// frontend/src/api/client.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type {
  ConjunctionResponse,
  ConjunctionDetailResponse,
  SatelliteResponse,
  PropagateResponse,
  MLCompareResponse,
  AlertConfigResponse,
} from "./types";

const BASE = "";

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  if (res.status === 204) return undefined as T;
  return res.json();
}

// --- Satellites ---
export function useSatellites(search?: string, regime?: string) {
  return useQuery({
    queryKey: ["satellites", search, regime],
    queryFn: () => {
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      if (regime) params.set("regime", regime);
      return fetchJSON<{ items: SatelliteResponse[]; total: number }>(
        `/api/satellites?${params}`
      );
    },
  });
}

// --- Conjunctions ---
export function useConjunctions(minPc?: number, hoursAhead = 72) {
  return useQuery({
    queryKey: ["conjunctions", minPc, hoursAhead],
    queryFn: () => {
      const params = new URLSearchParams();
      if (minPc !== undefined) params.set("min_pc", String(minPc));
      params.set("hours_ahead", String(hoursAhead));
      return fetchJSON<ConjunctionResponse[]>(`/api/conjunctions?${params}`);
    },
  });
}

export function useConjunctionDetail(id: number | null) {
  return useQuery({
    queryKey: ["conjunction", id],
    queryFn: () => fetchJSON<ConjunctionDetailResponse>(`/api/conjunctions/${id}`),
    enabled: id !== null,
  });
}

// --- Propagation ---
export function usePropagate(noradIds: number[], durationHours = 2, stepMinutes = 1) {
  return useQuery({
    queryKey: ["propagate", noradIds, durationHours, stepMinutes],
    queryFn: () =>
      fetchJSON<PropagateResponse[]>("/api/propagate", {
        method: "POST",
        body: JSON.stringify({
          norad_ids: noradIds,
          duration_hours: durationHours,
          step_minutes: stepMinutes,
        }),
      }),
    enabled: noradIds.length > 0,
  });
}

// --- ML Compare ---
export function useMLCompare(conjunctionId: number | null) {
  return useQuery({
    queryKey: ["ml-compare", conjunctionId],
    queryFn: () => fetchJSON<MLCompareResponse>(`/api/ml/compare/${conjunctionId}`),
    enabled: conjunctionId !== null,
  });
}

// --- Alerts ---
export function useAlerts() {
  return useQuery({
    queryKey: ["alerts"],
    queryFn: () => fetchJSON<AlertConfigResponse[]>("/api/alerts"),
  });
}

export function useCreateAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Omit<AlertConfigResponse, "id">) =>
      fetchJSON<AlertConfigResponse>("/api/alerts", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

export function useUpdateAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: AlertConfigResponse) =>
      fetchJSON<AlertConfigResponse>(`/api/alerts/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

export function useDeleteAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      fetchJSON<void>(`/api/alerts/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
}
```

- [ ] **Step 3: Create Zustand store**

```typescript
// frontend/src/stores/colliderStore.ts
import { create } from "zustand";

interface ColliderStore {
  selectedConjunctionId: number | null;
  selectConjunction: (id: number | null) => void;
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  alertModalOpen: boolean;
  setAlertModalOpen: (open: boolean) => void;
}

export const useColliderStore = create<ColliderStore>((set) => ({
  selectedConjunctionId: null,
  selectConjunction: (id) => set({ selectedConjunctionId: id }),
  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  alertModalOpen: false,
  setAlertModalOpen: (open) => set({ alertModalOpen: open }),
}));
```

- [ ] **Step 4: Commit**

```bash
cd frontend && git add src/api/types.ts src/api/client.ts src/stores/colliderStore.ts
git commit -m "feat: TypeScript types, React Query hooks, Zustand store"
```

---

## Task 10: Header + App Layout Shell

**Files:**
- Create: `frontend/src/components/Header.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create Header component**

```tsx
// frontend/src/components/Header.tsx
import { useState } from "react";
import { useSatellites } from "../api/client";
import { useColliderStore } from "../stores/colliderStore";

export default function Header() {
  const [search, setSearch] = useState("");
  const { data } = useSatellites(search || undefined);
  const setAlertModalOpen = useColliderStore((s) => s.setAlertModalOpen);

  return (
    <header className="flex items-center justify-between px-4 py-2 bg-[var(--color-bg-secondary)] border-b border-[var(--color-border)]">
      <div className="flex items-center gap-3">
        <div className="text-xl font-bold tracking-wide text-[var(--color-accent)]">
          COLLIDER
        </div>
        <span className="text-xs text-[var(--color-text-secondary)]">
          Collision Avoidance System
        </span>
      </div>

      <div className="relative">
        <input
          type="text"
          placeholder="Search satellites..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-64 px-3 py-1.5 text-sm rounded bg-[var(--color-bg-primary)] border border-[var(--color-border)] text-[var(--color-text-primary)] placeholder-[var(--color-text-secondary)] focus:outline-none focus:border-[var(--color-accent)]"
        />
        {search && data?.items && data.items.length > 0 && (
          <div className="absolute top-full left-0 mt-1 w-full bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded shadow-lg z-50 max-h-48 overflow-y-auto">
            {data.items.slice(0, 8).map((sat) => (
              <div
                key={sat.norad_id}
                className="px-3 py-1.5 text-sm hover:bg-[var(--color-bg-secondary)] cursor-pointer"
                onClick={() => setSearch("")}
              >
                <span className="text-[var(--color-text-primary)]">{sat.name}</span>
                <span className="ml-2 text-[var(--color-text-secondary)]">
                  #{sat.norad_id}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={() => setAlertModalOpen(true)}
          className="px-3 py-1.5 text-sm rounded bg-[var(--color-bg-card)] border border-[var(--color-border)] hover:border-[var(--color-accent)] transition-colors"
        >
          Alerts
        </button>
        <div className="flex items-center gap-1.5 text-xs text-[var(--color-text-secondary)]">
          <span className="w-2 h-2 rounded-full bg-[var(--color-risk-low)]" />
          Connected
        </div>
      </div>
    </header>
  );
}
```

- [ ] **Step 2: Rewrite App.tsx with layout shell**

```tsx
// frontend/src/App.tsx
import Header from "./components/Header";

function App() {
  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        {/* Left panel — ConjunctionTimeline (Task 11) */}
        <aside className="w-80 border-r border-[var(--color-border)] overflow-y-auto bg-[var(--color-bg-secondary)]">
          <div className="p-4 text-sm text-[var(--color-text-secondary)]">
            Loading conjunctions...
          </div>
        </aside>

        {/* Right panel — Globe + Detail */}
        <main className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 bg-[var(--color-bg-primary)]">
            {/* GlobeView (Task 12) */}
            <div className="flex items-center justify-center h-full text-[var(--color-text-secondary)]">
              Globe loading...
            </div>
          </div>
          <div className="h-64 border-t border-[var(--color-border)] bg-[var(--color-bg-secondary)] overflow-y-auto">
            {/* EventDetailPanel (Task 13) */}
            <div className="p-4 text-sm text-[var(--color-text-secondary)]">
              Select a conjunction to view details
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;
```

- [ ] **Step 3: Verify it builds**

Run: `cd frontend && npm run build`
Expected: BUILD SUCCESS

- [ ] **Step 4: Commit**

```bash
cd frontend && git add src/components/Header.tsx src/App.tsx
git commit -m "feat: Header component and app layout shell"
```

---

## Task 11: ConjunctionTimeline + ConjunctionCard Components

**Files:**
- Create: `frontend/src/components/ConjunctionTimeline.tsx`
- Create: `frontend/src/components/ConjunctionCard.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create ConjunctionCard**

```tsx
// frontend/src/components/ConjunctionCard.tsx
import type { ConjunctionResponse } from "../api/types";

function riskColor(pc: number | null): string {
  if (pc === null) return "var(--color-text-secondary)";
  if (pc >= 1e-4) return "var(--color-risk-high)";
  if (pc >= 1e-6) return "var(--color-risk-medium)";
  return "var(--color-risk-low)";
}

function formatPc(pc: number | null): string {
  if (pc === null) return "N/A";
  return pc.toExponential(2);
}

function timeUntil(tca: string): string {
  const diff = new Date(tca).getTime() - Date.now();
  if (diff < 0) return "PASSED";
  const hours = Math.floor(diff / 3_600_000);
  const mins = Math.floor((diff % 3_600_000) / 60_000);
  if (hours > 24) return `${Math.floor(hours / 24)}d ${hours % 24}h`;
  return `${hours}h ${mins}m`;
}

interface Props {
  conjunction: ConjunctionResponse;
  selected: boolean;
  onClick: () => void;
}

export default function ConjunctionCard({ conjunction: c, selected, onClick }: Props) {
  const color = riskColor(c.pc_classical);

  return (
    <div
      onClick={onClick}
      className={`p-3 mx-2 my-1.5 rounded cursor-pointer border transition-colors ${
        selected
          ? "border-[var(--color-accent)] bg-[var(--color-bg-card)]"
          : "border-transparent hover:bg-[var(--color-bg-card)]"
      }`}
    >
      <div className="flex justify-between items-start">
        <div className="text-sm font-medium">
          {c.primary_name || `#${c.primary_norad_id}`}
          <span className="text-[var(--color-text-secondary)]"> vs </span>
          {c.secondary_name || `#${c.secondary_norad_id}`}
        </div>
        <span className="text-xs font-mono" style={{ color }}>
          {formatPc(c.pc_classical)}
        </span>
      </div>
      <div className="flex justify-between mt-1.5 text-xs text-[var(--color-text-secondary)]">
        <span>
          {c.miss_distance_km !== null
            ? `${c.miss_distance_km.toFixed(3)} km`
            : "—"}
        </span>
        <span>{timeUntil(c.tca)}</span>
      </div>
      <div
        className="mt-1.5 h-0.5 rounded-full"
        style={{ backgroundColor: color, opacity: 0.6 }}
      />
    </div>
  );
}
```

- [ ] **Step 2: Create ConjunctionTimeline**

```tsx
// frontend/src/components/ConjunctionTimeline.tsx
import { useConjunctions } from "../api/client";
import { useColliderStore } from "../stores/colliderStore";
import ConjunctionCard from "./ConjunctionCard";

export default function ConjunctionTimeline() {
  const { data: conjunctions, isLoading, error } = useConjunctions();
  const selectedId = useColliderStore((s) => s.selectedConjunctionId);
  const select = useColliderStore((s) => s.selectConjunction);

  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b border-[var(--color-border)]">
        <h2 className="text-sm font-semibold tracking-wide uppercase text-[var(--color-text-secondary)]">
          Conjunctions
        </h2>
        <p className="text-xs text-[var(--color-text-secondary)] mt-0.5">
          Sorted by collision probability
        </p>
      </div>

      <div className="flex-1 overflow-y-auto">
        {isLoading && (
          <div className="p-4 text-sm text-[var(--color-text-secondary)]">
            Loading...
          </div>
        )}
        {error && (
          <div className="p-4 text-sm text-[var(--color-risk-high)]">
            Failed to load conjunctions
          </div>
        )}
        {conjunctions?.map((c) => (
          <ConjunctionCard
            key={c.id}
            conjunction={c}
            selected={c.id === selectedId}
            onClick={() => select(c.id)}
          />
        ))}
        {conjunctions && conjunctions.length === 0 && (
          <div className="p-4 text-sm text-[var(--color-text-secondary)]">
            No upcoming conjunctions
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Wire into App.tsx**

Replace the left panel placeholder in `App.tsx`:

```tsx
// Replace the <aside> contents
import ConjunctionTimeline from "./components/ConjunctionTimeline";
// ...
<aside className="w-80 border-r border-[var(--color-border)] overflow-y-auto bg-[var(--color-bg-secondary)]">
  <ConjunctionTimeline />
</aside>
```

- [ ] **Step 4: Verify it builds**

Run: `cd frontend && npm run build`
Expected: BUILD SUCCESS

- [ ] **Step 5: Commit**

```bash
cd frontend && git add src/components/ConjunctionTimeline.tsx src/components/ConjunctionCard.tsx src/App.tsx
git commit -m "feat: ConjunctionTimeline and ConjunctionCard components"
```

---

## Task 12: CesiumJS GlobeView Component

**Files:**
- Create: `frontend/src/components/GlobeView.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create GlobeView component**

```tsx
// frontend/src/components/GlobeView.tsx
import { useMemo } from "react";
import { Viewer, Entity, PolylineGraphics } from "resium";
import {
  Cartesian3,
  Color,
  JulianDate,
  SampledPositionProperty,
  ClockRange,
  ClockStep,
} from "cesium";
import { usePropagate } from "../api/client";
import { useColliderStore } from "../stores/colliderStore";
import { useConjunctions } from "../api/client";
import type { PropagateResponse } from "../api/types";

function riskCesiumColor(pc: number | null): Color {
  if (pc === null) return Color.GRAY;
  if (pc >= 1e-4) return Color.RED.withAlpha(0.9);
  if (pc >= 1e-6) return Color.YELLOW.withAlpha(0.8);
  return Color.GREEN.withAlpha(0.7);
}

function buildOrbitPositionProperty(positions: PropagateResponse["positions"]) {
  const property = new SampledPositionProperty();
  for (const p of positions) {
    const time = JulianDate.fromIso8601(p.epoch);
    const pos = Cartesian3.fromDegrees(p.lon_deg, p.lat_deg, p.alt_km * 1000);
    property.addSample(time, pos);
  }
  return property;
}

export default function GlobeView() {
  const { data: conjunctions } = useConjunctions();
  const selectedId = useColliderStore((s) => s.selectedConjunctionId);

  // Collect NORAD IDs to propagate from top conjunctions
  const noradIds = useMemo(() => {
    if (!conjunctions) return [];
    const ids = new Set<number>();
    for (const c of conjunctions.slice(0, 10)) {
      ids.add(c.primary_norad_id);
      ids.add(c.secondary_norad_id);
    }
    return Array.from(ids);
  }, [conjunctions]);

  const { data: propagation } = usePropagate(noradIds, 2, 1);

  // Find selected conjunction's satellite IDs for highlighting
  const selectedConj = conjunctions?.find((c) => c.id === selectedId);

  return (
    <Viewer
      full
      timeline={false}
      animation={false}
      homeButton={false}
      baseLayerPicker={false}
      navigationHelpButton={false}
      sceneModePicker={false}
      geocoder={false}
      selectionIndicator={false}
      infoBox={false}
      style={{ height: "100%", width: "100%" }}
    >
      {propagation?.map((sat) => {
        if (sat.positions.length < 2) return null;

        const isSelected =
          selectedConj &&
          (sat.norad_id === selectedConj.primary_norad_id ||
            sat.norad_id === selectedConj.secondary_norad_id);

        const pc = conjunctions?.find(
          (c) =>
            c.primary_norad_id === sat.norad_id ||
            c.secondary_norad_id === sat.norad_id
        )?.pc_classical;

        const color = riskCesiumColor(pc ?? null);
        const width = isSelected ? 3 : 1;

        const positions = sat.positions.map((p) =>
          Cartesian3.fromDegrees(p.lon_deg, p.lat_deg, p.alt_km * 1000)
        );

        return (
          <Entity key={sat.norad_id} name={`Satellite #${sat.norad_id}`}>
            <PolylineGraphics
              positions={positions}
              width={width}
              material={isSelected ? Color.CYAN : color}
            />
          </Entity>
        );
      })}
    </Viewer>
  );
}
```

- [ ] **Step 2: Wire into App.tsx**

Replace the globe placeholder in `App.tsx`:

```tsx
import GlobeView from "./components/GlobeView";
// ...
<div className="flex-1 bg-[var(--color-bg-primary)]">
  <GlobeView />
</div>
```

- [ ] **Step 3: Verify it builds**

Run: `cd frontend && npm run build`
Expected: BUILD SUCCESS

- [ ] **Step 4: Commit**

```bash
cd frontend && git add src/components/GlobeView.tsx src/App.tsx
git commit -m "feat: CesiumJS GlobeView with orbit tracks and risk coloring"
```

---

## Task 13: EventDetailPanel + PcComparisonChart

**Files:**
- Create: `frontend/src/components/EventDetailPanel.tsx`
- Create: `frontend/src/components/PcComparisonChart.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create PcComparisonChart**

```tsx
// frontend/src/components/PcComparisonChart.tsx
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { MLCompareResponse } from "../api/types";

interface Props {
  data: MLCompareResponse;
}

export default function PcComparisonChart({ data }: Props) {
  const chartData = [
    {
      name: "Classical",
      pc: data.pc_classical ? Math.log10(data.pc_classical) : null,
      raw: data.pc_classical,
    },
    {
      name: "ML Enhanced",
      pc: data.pc_ml ? Math.log10(data.pc_ml) : null,
      raw: data.pc_ml,
    },
  ];

  return (
    <div>
      <div className="flex justify-between items-center mb-2">
        <h4 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase">
          Pc Comparison (log₁₀)
        </h4>
        {data.confidence !== null && (
          <span className="text-xs text-[var(--color-text-secondary)]">
            Agreement: {(data.confidence * 100).toFixed(0)}%
          </span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={120}>
        <BarChart data={chartData} layout="vertical">
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis
            type="number"
            domain={[-10, 0]}
            tick={{ fontSize: 10, fill: "var(--color-text-secondary)" }}
          />
          <YAxis
            dataKey="name"
            type="category"
            width={80}
            tick={{ fontSize: 10, fill: "var(--color-text-secondary)" }}
          />
          <Tooltip
            formatter={(value: number, name: string, props: any) =>
              props.payload.raw ? props.payload.raw.toExponential(2) : "N/A"
            }
            contentStyle={{
              backgroundColor: "var(--color-bg-card)",
              border: "1px solid var(--color-border)",
              fontSize: 12,
            }}
          />
          <Bar dataKey="pc" fill="var(--color-accent)" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 2: Create EventDetailPanel**

```tsx
// frontend/src/components/EventDetailPanel.tsx
import { useColliderStore } from "../stores/colliderStore";
import { useConjunctionDetail, useMLCompare } from "../api/client";
import PcComparisonChart from "./PcComparisonChart";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZoneName: "short",
  });
}

function riskBadge(label: string) {
  const colors: Record<string, string> = {
    low: "bg-green-900 text-green-300",
    medium: "bg-yellow-900 text-yellow-300",
    high: "bg-red-900 text-red-300",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[label] || ""}`}>
      {label.toUpperCase()}
    </span>
  );
}

export default function EventDetailPanel() {
  const selectedId = useColliderStore((s) => s.selectedConjunctionId);
  const { data: detail, isLoading } = useConjunctionDetail(selectedId);
  const { data: mlData } = useMLCompare(selectedId);

  if (!selectedId) {
    return (
      <div className="p-4 text-sm text-[var(--color-text-secondary)]">
        Select a conjunction to view details
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="p-4 text-sm text-[var(--color-text-secondary)]">Loading...</div>
    );
  }

  if (!detail) return null;

  return (
    <div className="p-4 grid grid-cols-2 gap-4">
      {/* Left: Geometry info */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <h3 className="text-sm font-semibold">
            {detail.primary_name || `#${detail.primary_norad_id}`}
            {" vs "}
            {detail.secondary_name || `#${detail.secondary_norad_id}`}
          </h3>
          {mlData && riskBadge(mlData.risk_label)}
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <span className="text-[var(--color-text-secondary)]">TCA</span>
            <div>{formatDate(detail.tca)}</div>
          </div>
          <div>
            <span className="text-[var(--color-text-secondary)]">Miss Distance</span>
            <div>
              {detail.miss_distance_km !== null
                ? `${detail.miss_distance_km.toFixed(3)} km`
                : "—"}
            </div>
          </div>
          <div>
            <span className="text-[var(--color-text-secondary)]">Relative Velocity</span>
            <div>
              {detail.relative_velocity_kms !== null
                ? `${detail.relative_velocity_kms.toFixed(2)} km/s`
                : "—"}
            </div>
          </div>
          <div>
            <span className="text-[var(--color-text-secondary)]">Classical Pc</span>
            <div>
              {detail.pc_classical !== null
                ? detail.pc_classical.toExponential(2)
                : "—"}
            </div>
          </div>
        </div>

        {detail.cdm_history.length > 0 && (
          <div className="mt-3">
            <h4 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase mb-1">
              CDM History ({detail.cdm_history.length})
            </h4>
            <div className="max-h-20 overflow-y-auto text-xs space-y-0.5">
              {detail.cdm_history.map((cdm) => (
                <div key={cdm.id} className="flex justify-between">
                  <span>{cdm.cdm_timestamp ? formatDate(cdm.cdm_timestamp) : "—"}</span>
                  <span>{cdm.pc ? cdm.pc.toExponential(2) : "—"}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Right: ML comparison chart */}
      <div>{mlData && <PcComparisonChart data={mlData} />}</div>
    </div>
  );
}
```

- [ ] **Step 3: Wire into App.tsx**

Replace the bottom panel placeholder:

```tsx
import EventDetailPanel from "./components/EventDetailPanel";
// ...
<div className="h-64 border-t border-[var(--color-border)] bg-[var(--color-bg-secondary)] overflow-y-auto">
  <EventDetailPanel />
</div>
```

- [ ] **Step 4: Verify it builds**

Run: `cd frontend && npm run build`
Expected: BUILD SUCCESS

- [ ] **Step 5: Commit**

```bash
cd frontend && git add src/components/EventDetailPanel.tsx src/components/PcComparisonChart.tsx src/App.tsx
git commit -m "feat: EventDetailPanel with ML vs Classical Pc chart"
```

---

## Task 14: AlertConfigForm Component

**Files:**
- Create: `frontend/src/components/AlertConfigForm.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create AlertConfigForm modal**

```tsx
// frontend/src/components/AlertConfigForm.tsx
import { useState } from "react";
import { useAlerts, useCreateAlert, useDeleteAlert } from "../api/client";
import { useColliderStore } from "../stores/colliderStore";

export default function AlertConfigForm() {
  const open = useColliderStore((s) => s.alertModalOpen);
  const setOpen = useColliderStore((s) => s.setAlertModalOpen);
  const { data: alerts, isLoading } = useAlerts();
  const createAlert = useCreateAlert();
  const deleteAlert = useDeleteAlert();

  const [threshold, setThreshold] = useState("1e-4");
  const [noradIds, setNoradIds] = useState("");
  const [email, setEmail] = useState("");

  if (!open) return null;

  const handleCreate = () => {
    createAlert.mutate({
      watched_norad_ids: noradIds
        ? noradIds.split(",").map((s) => parseInt(s.trim(), 10))
        : null,
      pc_threshold: parseFloat(threshold),
      notification_channels: email ? { email } : null,
      enabled: true,
    });
    setThreshold("1e-4");
    setNoradIds("");
    setEmail("");
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={() => setOpen(false)}
    >
      <div
        className="w-[480px] bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center p-4 border-b border-[var(--color-border)]">
          <h2 className="text-sm font-semibold">Alert Configuration</h2>
          <button
            onClick={() => setOpen(false)}
            className="text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
          >
            ✕
          </button>
        </div>

        {/* Create form */}
        <div className="p-4 space-y-3 border-b border-[var(--color-border)]">
          <div>
            <label className="block text-xs text-[var(--color-text-secondary)] mb-1">
              Pc Threshold
            </label>
            <input
              type="text"
              value={threshold}
              onChange={(e) => setThreshold(e.target.value)}
              className="w-full px-2 py-1 text-sm rounded bg-[var(--color-bg-primary)] border border-[var(--color-border)] text-[var(--color-text-primary)]"
            />
          </div>
          <div>
            <label className="block text-xs text-[var(--color-text-secondary)] mb-1">
              Watch NORAD IDs (comma-separated, optional)
            </label>
            <input
              type="text"
              value={noradIds}
              onChange={(e) => setNoradIds(e.target.value)}
              placeholder="25544, 48274"
              className="w-full px-2 py-1 text-sm rounded bg-[var(--color-bg-primary)] border border-[var(--color-border)] text-[var(--color-text-primary)]"
            />
          </div>
          <div>
            <label className="block text-xs text-[var(--color-text-secondary)] mb-1">
              Email (optional)
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-2 py-1 text-sm rounded bg-[var(--color-bg-primary)] border border-[var(--color-border)] text-[var(--color-text-primary)]"
            />
          </div>
          <button
            onClick={handleCreate}
            className="w-full py-1.5 text-sm rounded bg-[var(--color-accent)] text-white hover:opacity-90 transition-opacity"
          >
            Create Alert
          </button>
        </div>

        {/* Existing alerts */}
        <div className="p-4 max-h-48 overflow-y-auto">
          <h3 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase mb-2">
            Active Alerts
          </h3>
          {isLoading && <div className="text-xs text-[var(--color-text-secondary)]">Loading...</div>}
          {alerts?.length === 0 && (
            <div className="text-xs text-[var(--color-text-secondary)]">No alerts configured</div>
          )}
          {alerts?.map((a) => (
            <div
              key={a.id}
              className="flex justify-between items-center py-1.5 border-b border-[var(--color-border)] last:border-0"
            >
              <div className="text-xs">
                <span>Pc ≥ {a.pc_threshold.toExponential(1)}</span>
                {a.watched_norad_ids && (
                  <span className="ml-2 text-[var(--color-text-secondary)]">
                    [{a.watched_norad_ids.join(", ")}]
                  </span>
                )}
              </div>
              <button
                onClick={() => deleteAlert.mutate(a.id)}
                className="text-xs text-[var(--color-risk-high)] hover:underline"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Wire into App.tsx**

Add at the bottom of the App component, before the closing `</div>`:

```tsx
import AlertConfigForm from "./components/AlertConfigForm";
// ...at end of App return, before closing </div>:
<AlertConfigForm />
```

- [ ] **Step 3: Verify it builds**

Run: `cd frontend && npm run build`
Expected: BUILD SUCCESS

- [ ] **Step 4: Commit**

```bash
cd frontend && git add src/components/AlertConfigForm.tsx src/App.tsx
git commit -m "feat: AlertConfigForm modal with CRUD"
```

---

## Task 15: Final Integration — Delete Boilerplate + Full App.tsx

**Files:**
- Modify: `frontend/src/App.tsx` (final version with all imports)
- Delete: `frontend/src/App.css` (replaced by Tailwind)
- Delete: `frontend/src/assets/react.svg` (unused)
- Delete: `frontend/public/vite.svg` (unused)

- [ ] **Step 1: Write final App.tsx**

```tsx
// frontend/src/App.tsx
import Header from "./components/Header";
import ConjunctionTimeline from "./components/ConjunctionTimeline";
import GlobeView from "./components/GlobeView";
import EventDetailPanel from "./components/EventDetailPanel";
import AlertConfigForm from "./components/AlertConfigForm";

export default function App() {
  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <aside className="w-80 border-r border-[var(--color-border)] overflow-y-auto bg-[var(--color-bg-secondary)]">
          <ConjunctionTimeline />
        </aside>
        <main className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 bg-[var(--color-bg-primary)]">
            <GlobeView />
          </div>
          <div className="h-64 border-t border-[var(--color-border)] bg-[var(--color-bg-secondary)] overflow-y-auto">
            <EventDetailPanel />
          </div>
        </main>
      </div>
      <AlertConfigForm />
    </div>
  );
}
```

- [ ] **Step 2: Remove boilerplate**

```bash
rm -f frontend/src/App.css frontend/src/assets/react.svg frontend/public/vite.svg
```

- [ ] **Step 3: Verify full build**

```bash
cd frontend && npm run build
```
Expected: BUILD SUCCESS

- [ ] **Step 4: Verify backend tests all pass**

```bash
cd backend && python -m pytest -v
```
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd frontend && git add -A && cd ..
git add -A
git commit -m "feat: complete Phase 5 — API routes + React frontend dashboard"
```

---

## Task 16: Local Demo Smoke Test

- [ ] **Step 1: Start infrastructure**

```bash
docker-compose up -d postgres redis
```

- [ ] **Step 2: Run Alembic migrations**

```bash
cd backend && alembic upgrade head
```

- [ ] **Step 3: Start backend**

```bash
cd backend && uvicorn src.main:app --reload
```

Verify: `curl http://localhost:8000/health` → `{"status":"ok","service":"collider"}`
Verify: `curl http://localhost:8000/api/satellites?limit=5` → `{"items":[],"total":0,...}`
Verify: `curl http://localhost:8000/api/conjunctions` → `[]`

- [ ] **Step 4: Start frontend**

```bash
cd frontend && npm run dev
```

Verify: Open `http://localhost:5173` — should see dark-themed dashboard with COLLIDER header, empty conjunction timeline, CesiumJS globe rendering.

- [ ] **Step 5: Seed test data (optional)**

```bash
cd backend && celery -A src.ingestion.tasks worker --loglevel=info
```

Or run the ingestion tasks manually to populate data, then verify the dashboard shows conjunction cards and orbit tracks on the globe.
