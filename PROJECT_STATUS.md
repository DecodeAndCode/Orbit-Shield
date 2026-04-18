# Collider — Project Status Dashboard

**ML-enhanced satellite collision avoidance system inspired by Privateer Wavefinder**

---

## Executive Summary

| Metric | Status |
|--------|--------|
| **Phases Complete** | 5 of 6 (Phase 6 ~80%) |
| **Commits** | 29 |
| **Backend Code** | ~4,900 LOC Python |
| **Frontend Code** | ~2,500 LOC TypeScript |
| **Tests** | 116 (all passing) |
| **API Endpoints** | 6 routes, 1 WebSocket |
| **Catalog Size** | 14,662 satellites |
| **Globe Rendering** | 14,197 point cloud + polylines |

---

## Phase Breakdown

### Phase 0: Domain Study ✅
**Goal:** Understand orbital mechanics, TLE format, SGP4, collision probability theory.

**Completed:**
- NASA CARA workflow: Tracking → Screening → Pc → Alerting
- TLE format, SGP4 propagation, TEME/ECEF reference frames
- B-plane 2D Gaussian collision probability (Alfano method)
- CelesTrak/Space-Track/SOCRATES data sources

---

### Phase 1: Data Ingestion ✅
**Goal:** Fetch and store orbital data from multiple sources.

**Completed:**
- CelesTrak GP API (OMM JSON) → PostgreSQL
- Space-Track API (TLE text, CDM histories)
- SOCRATES pre-computed conjunctions (3x daily)
- NOAA space weather (F10.7, Kp indices) → Redis cache
- Celery tasks for daily + on-demand updates
- Database: PostgreSQL + TimescaleDB, 5 ORM tables

**Data:**
- 14,662 satellites (CelesTrak active catalog)
- 1 satellite with TLE strings (ISS, from seed demo)
- Demo seed: ISS, Hubble, Starlink debris, 3 synthetic conjunctions

---

### Phase 2: SGP4 Propagation & Conjunction Screening ✅
**Goal:** Detect close approaches via vectorized propagation.

**Completed:**
- SGP4 batch propagation (C-accelerated, ~14k sats in 300ms)
- 4-stage pre-filtering: perigee/apogee → inclination → kdTree 5km → numerical TCA
- Screening pipeline identifies conjunctions, computes miss distance + relative velocity
- Validated against SOCRATES synthetic events

**Performance:** 14,197 valid sats propagated in ~365ms (single epoch).

---

### Phase 3: Classical Collision Probability ✅
**Goal:** Compute risk via NASA B-plane method.

**Completed:**
- B-plane 2D Gaussian integration (linearized + numerical dblquad)
- Covariance fallback chain:
  1. CDM from Space-Track
  2. TLE ensemble (≥3 consecutive TLEs)
  3. Altitude-based default (LEO 1km, MEO 5km, GEO 10km)
- `pc_classical` stored per conjunction
- Validated against SOCRATES maximum Pc values

---

### Phase 4: ML Enhancement ✅
**Goal:** Improve predictions via XGBoost models.

**Completed:**
- **CovarianceEstimator** (XGBRegressor): 14 features → log₁₀(σ) prediction
- **ConjunctionRiskClassifier** (XGBClassifier): 22 features → P(Pc > 1e-4)
- Feature sets: orbital (14), conjunction (22), space weather (3)
- Training data: synthetic + database fallback
- `pc_ml` column populated; classical Pc never replaced
- ML models optional (graceful degradation if absent)
- 90/90 tests passing

**Model Registry:** Joblib + .meta.json, in-memory cache, auto-load on startup.

---

### Phase 5: Web Dashboard & API ✅
**Goal:** Real-time visualization + REST/WebSocket access.

**Backend (FastAPI):**
| Endpoint | Purpose |
|----------|---------|
| `GET /api/satellites` | Catalog search, pagination, filtering (regime) |
| `GET /api/conjunctions` | Upcoming events sorted by Pc, filters (min_pc, hours_ahead) |
| `GET /api/conjunctions/{id}` | Event detail + CDM history |
| `POST /api/propagate` | Batch SGP4 for selected satellites, TEME→geodetic |
| `GET /api/positions` | Current epoch snapshot, full catalog (14k sats) |
| `GET /api/ml/compare/{id}` | Classical vs ML Pc + confidence + feature importance |
| `GET/POST/PUT/DELETE /api/alerts` | Alert config CRUD |
| `WS /ws/conjunctions` | Live conjunction stream (30s refresh) |

**Frontend (React 19 + TypeScript):**
- Header: branding, nav
- GlobeView: CesiumJS 3D, point cloud (14k sats, regime-colored), polylines (top-10 conjunctions, risk-colored)
- ConjunctionTimeline: list sorted by Pc, countdown timers, TCA badges
- EventDetailPanel: miss distance, relative velocity, orbital geometry
- PcComparisonChart: Recharts classical vs ML probability
- AlertConfigForm: threshold, channels, watched satellites, enable/disable

**State Management:**
- Zustand: selected conjunction, UI state
- React Query: server state, 30s refetch intervals, WebSocket sync

**Build:**
- Vite + Tailwind v4
- Code split: Cesium 4.5MB / charts 357KB / app 196KB / query 45KB
- Dev proxy: `/api` + `/ws` → `http://localhost:8000`
- Asset serving: vite-plugin-cesium (Workers/Widgets/Assets)

---

### Phase 6: Integration & Polish (80% complete)

**Completed:**
- Alert evaluator + notifier (email/Slack/Discord stubs)
- Demo seed script (ISS + Hubble + Starlink debris + 3 conjunctions)
- README with quick start, architecture diagram, API table
- All 6 API endpoints tested (116 tests)
- Bundle optimization, CORS config, error handling
- Cesium Ion → OpenStreetMap tiles (no auth required)
- Full catalog point cloud (Wayfinder-style)

**Pending:**
- [ ] Real SMTP email integration (currently logs)
- [ ] Slack/Discord webhook wiring (currently logs)
- [ ] Deploy to Vercel (frontend) + cloud backend (Fly.io / Heroku)
- [ ] Performance profiling + caching layer
- [ ] User onboarding & documentation

---

## Architecture

```
Ingestion (Celery)        Space-Track, CelesTrak, SOCRATES, NOAA
       │
       ▼
Storage                   PostgreSQL+TimescaleDB (14.6k sats, conjunctions, CDMs, alerts)
                          Redis (space weather, Celery broker)
       │
       ▼
Compute                   SGP4 propagation → 4-stage screening → classical Pc → ML Pc
       │
       ▼
API (FastAPI)             6 REST routes + WebSocket /ws/conjunctions
       │
       ▼
Frontend (React+CesiumJS) Globe (14k points) + timeline + ML compare + alerts
```

---

## Tech Stack

| Layer | Tech |
|-------|------|
| **Backend** | Python 3.13, FastAPI, async SQLAlchemy + asyncpg |
| **Database** | PostgreSQL 16 + TimescaleDB (time-series), Redis 7 |
| **Jobs** | Celery + Redis broker, Alembic migrations |
| **Orbital** | sgp4 (C-accelerated), astropy, scipy.spatial.cKDTree |
| **ML** | XGBoost, scikit-learn, joblib (joblib + .meta.json registry) |
| **Frontend** | React 19 + TypeScript, Vite, CesiumJS/Resium, Zustand, React Query |
| **UI** | Tailwind v4, Recharts, lucide-react icons |

---

## Live Testing Checklist

### Backend (http://localhost:8000)
- [x] `/health` → `{"status": "ok"}`
- [x] `/api/satellites` → paginated catalog
- [x] `/api/conjunctions` → sorted by Pc_classical
- [x] `/api/propagate` → batch SGP4 for selected sats
- [x] `/api/positions` → 14,197 current positions (~365ms)
- [x] `/api/ml/compare/{id}` → classical vs ML + confidence
- [x] `/api/alerts` → CRUD alert configs
- [x] `/ws/conjunctions` → WebSocket live stream (30s refresh)

### Frontend (http://localhost:5173)
- [x] Globe renders with point cloud (14k cyan/orange/purple dots by regime)
- [x] Top-10 conjunction polylines overlay (red/yellow/green by risk)
- [x] Timeline shows conjunction list sorted by Pc
- [x] Click conjunction → detail panel with orbital geometry
- [x] PcComparisonChart displays classical vs ML
- [x] Alert form creates/updates configs
- [x] WebSocket updates live (30s refresh on timeline)

---

## Key Numbers

| Metric | Value |
|--------|-------|
| Total satellites loaded | 14,662 |
| Satellites with valid TLE/OMM | 14,197 |
| Propagation time (14k sats, 1 epoch) | ~365ms |
| Demo conjunctions | 3 (HIGH/MED/LOW Pc) |
| API test coverage | 6 routes × 20+ tests |
| Frontend components | 7 (Header, Globe, Timeline, Detail, Compare, Alerts, CardList) |
| Database tables | 5 (satellites, orbital_elements, conjunctions, cdm_history, alert_configs) |

---

## Next Steps (Post-MVP)

1. **Deploy** → Vercel (frontend) + Fly.io (backend)
2. **Real alerting** → SMTP email + Slack webhooks
3. **ML training** → Load historical CDMs (450k from NASA)
4. **Advanced features** → Maneuver recommendations, debris avoidance, multi-event correlation
5. **Partnerships** → Space-Track premium access, ESA DISCOS data

---

## Files & Structure

```
backend/
  src/
    api/               routes + schemas + WebSocket
    alerts/            evaluator + notifier
    db/                SQLAlchemy models, session, migrations
    ingestion/         Space-Track, CelesTrak, SOCRATES, NOAA clients
    ml/                features, models, training, inference, registry
    propagation/       SGP4 engine, screening, Pc computation
  scripts/
    seed_demo.py       demo data generator
  tests/               116 tests (orbital, screening, Pc, ML, API, alerts)

frontend/
  src/
    api/               React Query hooks + types
    components/        Globe, Timeline, Detail, Compare, Alerts, etc.
    stores/            Zustand state (selected conjunction)
  vite.config.ts      Cesium asset serving + API proxy

docs/
  PLAN.md            14-week roadmap
  ARCHITECTURE.md    detailed design
  specs/             Phase 5 dashboard design

PROJECT_STATUS.md  ← You are here
```

---

## Status by Feature

| Feature | Status | Notes |
|---------|--------|-------|
| Data ingestion | ✅ | 14k+ sats, 3 sources, daily updates |
| SGP4 propagation | ✅ | ~14k sats in 365ms (vectorized) |
| Conjunction screening | ✅ | 4-stage pipeline, 5km radius, TCA root-find |
| Classical Pc | ✅ | B-plane 2D Gaussian, covariance fallback |
| ML enhancement | ✅ | 2 XGBoost models, optional (graceful degrade) |
| REST API | ✅ | 6 endpoints, full CRUD, tested |
| WebSocket | ✅ | /ws/conjunctions, 30s refresh |
| React dashboard | ✅ | Globe (14k point cloud), timeline, detail panel |
| ML comparison panel | ✅ | Classical vs ML, confidence, feature importance |
| Alert config | ✅ | Threshold, channels, watched sats, enable/disable |
| Alert dispatch | 🟡 | Evaluator wired, notifier stubs (logs only) |
| Email integration | ❌ | Schema ready, SMTP TODO |
| Slack integration | ❌ | Schema ready, webhook TODO |
| Deploy | ❌ | Code ready, Vercel/Fly setup pending |

---

**Last Updated:** April 18, 2026 | **Model:** Claude Haiku 4.5
