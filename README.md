# Collider

ML-enhanced satellite collision avoidance. Ingests TLEs, propagates orbits via SGP4, screens for conjunctions, computes collision probability (Pc) classically and with ML enhancement, surfaces results in a real-time 3D dashboard.

Inspired by Privateer's Wavefinder.

---

## Stack

- **Backend** — Python 3.13, FastAPI, Celery+Redis, PostgreSQL+TimescaleDB, SQLAlchemy 2 async
- **Orbital** — sgp4, astropy, scipy.spatial.cKDTree
- **ML** — XGBoost (covariance + risk classification), scikit-learn, joblib
- **Frontend** — React 19 + TypeScript, Vite, CesiumJS/Resium, Zustand, React Query, Tailwind v4, Recharts

---

## Quick start (demo)

```bash
# 1. Infra
docker-compose up -d postgres redis

# 2. Backend deps + migrate + seed
cd backend
uv sync --extra ml --extra dev
uv run alembic upgrade head
uv run python scripts/seed_demo.py

# 3. Backend API
uv run uvicorn src.main:app --reload

# 4. Frontend (new terminal)
cd frontend && npm install && npm run dev
```

Open http://localhost:5173. Dashboard shows seeded ISS/Hubble/Starlink/debris and 3 conjunctions (HIGH/MED/LOW Pc).

---

## Architecture

5-layer flow, top to bottom:

```
Ingestion (Celery)        Space-Track, CelesTrak, SOCRATES, NOAA F10.7/Kp
       │
       ▼
Storage                   PostgreSQL+TimescaleDB (sats, TLEs, conjunctions, CDMs, alerts)
                          Redis (space weather cache, Celery broker)
       │
       ▼
Compute Engine            SGP4 propagation → 4-stage screening (perigee/apogee →
                          inclination → kdTree 5km → numerical TCA root-find)
                          → classical Pc (B-plane 2D Gaussian, Alfano method)
                          → ML covariance estimate (XGBRegressor)
                          → ML risk Pc (XGBClassifier)
       │
       ▼
API                       FastAPI REST (/api/satellites, /conjunctions, /propagate,
                          /ml/compare, /alerts) + WebSocket /ws/conjunctions
       │
       ▼
Frontend                  React + CesiumJS 3D globe, Pc-sorted conjunction timeline,
                          ML vs classical Pc comparison, alert config CRUD
```

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for diagram, schema, algorithm details.

---

## API

| Endpoint | Description |
|----------|-------------|
| `GET /api/satellites?search=&regime=&limit=&offset=` | Catalog list, paginated |
| `GET /api/conjunctions?min_pc=&hours_ahead=` | Upcoming conjunctions sorted by Pc |
| `GET /api/conjunctions/{id}` | Detail incl. CDM history |
| `POST /api/propagate` | TEME→geodetic positions for `norad_ids[]` |
| `GET /api/ml/compare/{conjunction_id}` | Classical vs ML Pc + agreement + risk label |
| `GET/POST/PUT/DELETE /api/alerts` | CRUD alert configs |
| `WS /ws/conjunctions` | Live conjunction stream (initial + 30s updates) |

OpenAPI: `http://localhost:8000/docs`.

---

## Domain notes

- All orbital math runs in **TEME**, converted to **GCRS/geodetic** at API boundary
- Screening prefilters cut 99%+ of pairs before kdTree query (radius 5 km)
- Classical Pc uses **B-plane 2D Gaussian integration** (NASA CARA / Alfano linearized)
- Covariance fallback chain: ML XGBRegressor → TLE ensemble (≥3 TLEs) → altitude-based default (LEO 1km, MEO 5km, GEO 10km)
- ML **enhances**, never replaces, classical Pc — the value column is `pc_ml`, classical stays in `pc_classical`
- Maneuver decision threshold: **Pc ≈ 1e-4** (industry convention)

---

## Tests

```bash
cd backend && uv run pytest -q
```

115 tests: orbital math, screening, classical Pc, ML pipeline, all 6 API routes, alert evaluator/notifier.

```bash
cd frontend && npm run build
```

TypeScript strict, no errors. Bundle split: cesium 4.5MB / charts 357KB / app 196KB / query 45KB.

---

## Status

- ✅ Phase 1 — Data ingestion (Space-Track, CelesTrak, SOCRATES, NOAA)
- ✅ Phase 2 — SGP4 propagation + 4-stage screening
- ✅ Phase 3 — Classical Pc (B-plane)
- ✅ Phase 4 — ML enhancement (covariance + risk)
- ✅ Phase 5 — REST API + WebSocket + React/Cesium dashboard
- 🟡 Phase 6 — Alerts (stubbed), demo seed, perf split, this README. Deploy pending.

See [`PLAN.md`](PLAN.md) for full roadmap.

---

## Layout

```
backend/
  src/
    api/         routes + schemas + websocket
    alerts/      evaluator + notifier (email/slack/discord)
    db/          SQLAlchemy models + session
    ingestion/   Space-Track, CelesTrak, SOCRATES, NOAA + Celery tasks
    ml/          features, models, training, inference, registry
    propagation/ SGP4, screening, probability, tasks
  scripts/seed_demo.py
  tests/        115 tests
frontend/
  src/
    api/         types + React Query hooks
    components/  Header, Timeline, GlobeView, EventDetailPanel, AlertConfigForm, PcComparisonChart
    stores/      Zustand store
```

---

## License

MIT.
