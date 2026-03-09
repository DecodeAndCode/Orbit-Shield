# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Collider** — ML-enhanced satellite collision avoidance system. Ingests real-time orbital data (TLEs), propagates trajectories via SGP4, screens for conjunctions, computes collision probability (Pc), and enhances predictions with ML. Inspired by Wavefinder by Privateer.

## Stack
- **Backend**: Python 3, FastAPI, Celery + Redis broker, PostgreSQL + TimescaleDB
- **Frontend**: React + TypeScript (Vite), CesiumJS/Resium, Recharts
- **ML**: PyTorch, torchdiffeq, XGBoost, scikit-learn, wandb
- **Orbital**: sgp4, astropy, skyfield, poliastro

## Commands
```bash
# Backend
cd backend && uvicorn src.main:app --reload
celery -A src.ingestion.tasks worker --loglevel=info

# Frontend
cd frontend && npm run dev

# Infrastructure
docker-compose up -d postgres redis

# Tests
cd backend && pytest
cd backend && pytest tests/test_screening.py -k "test_name"  # single test
cd frontend && npm test
```

## Code Style
- **Python**: Black formatter, type hints everywhere, Google-style docstrings
- **TypeScript**: ES modules, functional components with hooks, Zustand for state
- Prefer explicit over clever — this is safety-critical domain code

## Architecture

Monorepo with five layers flowing top-to-bottom. See `ARCHITECTURE.md` for the full diagram.

**Data Ingestion** (Celery workers) → **Storage** (PostgreSQL, TimescaleDB, Redis) → **Computation Engine** (SGP4 → Screening → Pc) → **API** (FastAPI REST + WebSocket) → **Frontend** (React + CesiumJS)

Key directories under `backend/src/`:
- `ingestion/` — Space-Track, CelesTrak, SOCRATES, NOAA fetchers + Celery tasks
- `propagation/` — SGP4 engine, conjunction screening (k-d tree), classical Pc (B-plane)
- `ml/` — Conjunction evolution prediction, orbit correction (Neural ODE/PINN), covariance estimation
- `api/routes/` — REST endpoints for catalog, conjunctions, propagation, alerts
- `alerts/` — Threshold evaluation, email/Slack notifications

Frontend under `frontend/src/`:
- `components/Globe/` — CesiumJS 3D orbit visualization
- `components/ConjunctionTimeline/` — Dashboard sorted by Pc
- `stores/` — Zustand state management

## Critical Domain Patterns
- All orbital computations use **TEME frame** internally, convert to **GCRS** for output
- Conjunction screening: `scipy.spatial.cKDTree` with **5 km radius** threshold
- Pre-filters before spatial search: perigee/apogee overlap → inclination filter → k-d tree → numerical TCA root-finding
- Classical Pc: **B-plane 2D Gaussian integration** (NASA CARA method)
- TLEs lack covariance — estimate from sequential TLE comparisons or use CDMs from Space-Track
- ML models **enhance** (not replace) classical Pc computation
- Maneuver decision threshold: Pc ~ **1e-4**

## Data Sources
- **Space-Track.org** (authenticated API) — full catalog, TLEs/OMMs, CDMs
- **CelesTrak** (open) — TLEs, SOCRATES conjunction reports (3x daily)
- **NOAA** — space weather (solar flux F10.7, geomagnetic indices)

## ML Tasks (priority order)
1. **Conjunction Evolution Prediction** — LSTM/Transformer on CDM sequences → will Pc exceed maneuver threshold?
2. **Orbit Propagation Correction** — Neural ODE/PINN residuals on top of SGP4
3. **TLE Covariance Estimation** — predict 3x3 position covariance from object/orbit metadata
4. **Space Weather → Drag Impact** — atmospheric density corrections from solar/geomagnetic data

## Planning Docs
- `ARCHITECTURE.md` — system diagram, tech stack rationale, DB schema, API endpoints, key algorithms
- `PLAN.md` — 14-week roadmap, milestone breakdown, data source details
