# Orbit-Shield

ML-enhanced satellite collision avoidance. Ingests TLEs and CDMs from Space-Track, propagates trajectories via SGP4, screens for conjunctions, computes collision probability (Pc) classically and with ML enhancement, surfaces results in a real-time 3D mission console.

Inspired by Privateer's Wayfinder.

## Stack

| Layer        | Tech                                                         |
| ------------ | ------------------------------------------------------------ |
| Frontend     | React 19 · TypeScript · Vite · Tailwind v4 · CesiumJS/Resium |
| Backend      | Python 3.12 · FastAPI (async) · SQLAlchemy 2 · asyncpg       |
| Task queue   | Celery + Redis                                               |
| Database     | PostgreSQL + TimescaleDB                                     |
| Orbital      | sgp4 · astropy · scipy (k-d tree screening + B-plane Pc)     |
| ML           | XGBoost (covariance estimator + conjunction risk classifier) |

## Quickstart

Requires Docker Desktop.

```bash
git clone https://github.com/DecodeAndCode/Orbit-Shield.git
cd Orbit-Shield
cp .env.example .env
# Edit .env: set SPACETRACK_USERNAME / SPACETRACK_PASSWORD
docker compose up -d
docker compose exec api alembic upgrade head
```

- API: http://localhost:8000 (docs at `/docs`)
- Frontend: http://localhost:5173
- Health: http://localhost:8000/health

## Local dev (no Docker)

```bash
docker compose up -d postgres redis              # infra only

cd backend
pip install -e ".[dev,ml]"
alembic upgrade head
uvicorn src.main:app --reload                              # API
celery -A src.ingestion.tasks worker --loglevel=info       # Worker
celery -A src.ingestion.tasks beat --loglevel=info         # Beat

cd frontend && npm install && npm run dev
```

## Real data

```bash
cd backend
python scripts/download_cdms.py --days 14
python -m src.ml.training.train_covariance
python -m src.ml.training.train_conjunction
```

## Architecture

Five layers:

1. **Ingestion** (Celery beat): Space-Track GP + CDMs, CelesTrak SOCRATES, NOAA space weather.
2. **Storage**: PostgreSQL + TimescaleDB hypertables, Redis cache + Celery broker.
3. **Compute**: SGP4 → k-d tree screening (5 km) → B-plane Pc (NASA CARA method).
4. **API**: FastAPI REST under `/api/*`.
5. **Frontend**: Mission-console UI on CesiumJS globe.

ML models **enhance** classical Pc, never replace it. Maneuver decision threshold: Pc ≈ 1e-4.

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for full diagram, schema, algorithms.

## Deploy

| Component | Target                                    |
| --------- | ----------------------------------------- |
| API       | Fly.io (`backend/fly.toml`)               |
| Worker    | Fly.io process group (same app)           |
| Postgres  | Neon (managed, free tier)                 |
| Redis     | Upstash (managed, free tier)              |
| Frontend  | Vercel (`frontend/vercel.json`)           |

```bash
cd backend
flyctl launch --no-deploy
flyctl secrets set DATABASE_URL=... REDIS_URL=... \
  CELERY_BROKER_URL=... CELERY_RESULT_BACKEND=... \
  SPACETRACK_USERNAME=... SPACETRACK_PASSWORD=...
flyctl deploy

cd ../frontend
vercel --prod
```

## Contributing

PRs welcome. CI runs `pytest` + `tsc --noEmit` + `npm run build` on push and PR; both must pass.

```bash
cd backend && pytest
cd frontend && npx tsc --noEmit && npm run build
```

Code style: Black + ruff (Python), TypeScript strict.

## License

MIT
