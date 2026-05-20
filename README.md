# Orbit-Shield

ML-enhanced satellite collision avoidance. Ingests TLEs and CDMs from Space-Track, propagates trajectories via SGP4, screens for conjunctions, computes collision probability (Pc) classically and with ML enhancement, and surfaces results on a real-time 3D mission console.

Inspired by Privateer's Wayfinder.

- Live frontend: <https://orbit-shield-seven.vercel.app>
- API: <https://orbit-shield-api.fly.dev> · OpenAPI at `/docs`

> ⚠️ **Not certified for operational collision avoidance.** Research / demonstration project. Do not use to make maneuver decisions for real spacecraft.

---

## Table of contents

- [Stack](#stack)
- [Quickstart (Docker)](#quickstart-docker)
- [Local development (no Docker)](#local-development-no-docker)
- [Loading real data](#loading-real-data)
- [Architecture](#architecture)
- [API surface](#api-surface)
- [Testing](#testing)
- [Deployment](#deployment)
- [Configuration reference](#configuration-reference)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [Security](#security)
- [License](#license)

---

## Stack

| Layer        | Tech                                                         |
| ------------ | ------------------------------------------------------------ |
| Frontend     | React 19 · TypeScript · Vite · Tailwind v4 · CesiumJS/Resium |
| Backend      | Python 3.12 · FastAPI (async) · SQLAlchemy 2 · asyncpg       |
| Task queue   | Celery + Redis                                               |
| Database     | PostgreSQL + TimescaleDB                                     |
| Orbital      | sgp4 · astropy · scipy (k-d tree screening + B-plane Pc)     |
| ML           | XGBoost (covariance estimator + conjunction risk classifier) |
| Infra        | Fly.io (API + worker + beat), Neon (Postgres), Upstash (Redis), Vercel (web) |

---

## Quickstart (Docker)

**Prerequisites:** Docker Desktop, Git, a free [Space-Track.org](https://www.space-track.org/) account.

```bash
git clone https://github.com/DecodeAndCode/Orbit-Shield.git
cd Orbit-Shield
cp .env.example .env
# Edit .env: set SPACETRACK_USERNAME / SPACETRACK_PASSWORD
docker compose up -d
docker compose exec api alembic upgrade head
```

- API → <http://localhost:8000> · OpenAPI at `/docs`
- Frontend → <http://localhost:5173>
- Health → <http://localhost:8000/health>

Tear down with `docker compose down -v` (the `-v` drops the Postgres volume too).

---

## Local development (no Docker)

**Prerequisites:** Python 3.12+, Node 20+, Docker (for Postgres + Redis only), [`uv`](https://docs.astral.sh/uv/) recommended for Python deps.

```bash
# 1. Infra
docker compose up -d postgres redis

# 2. Backend
cd backend
uv pip install -e ".[dev,ml]"     # or: pip install -e ".[dev,ml]"
alembic upgrade head
uvicorn src.main:app --reload     # API on :8000

# in a second shell
celery -A src.ingestion.tasks worker --loglevel=info

# in a third shell (optional — only for scheduled fetches)
celery -A src.ingestion.tasks beat --loglevel=info

# 3. Frontend
cd ../frontend
npm install
npm run dev                       # Vite on :5173
```

> macOS only: XGBoost requires `brew install libomp` for the OpenMP runtime.

---

## Loading real data

The ingestion tasks run automatically via Celery beat. To pull data on demand:

```bash
cd backend

# Pull full Space-Track GP catalog (~47k objects)
python -c "from src.ingestion.tasks import fetch_spacetrack_catalog; fetch_spacetrack_catalog.apply()"

# Run conjunction screening over the next 72 h
python -c "from src.propagation.tasks import run_conjunction_screening; run_conjunction_screening.apply()"

# Optional: train ML models on real data once you have ≥1k conjunctions
python -m src.ml.training.train_covariance
python -m src.ml.training.train_conjunction
```

---

## Architecture

Five layers, top to bottom:

1. **Ingestion** (Celery beat): Space-Track GP + CDMs, CelesTrak SOCRATES, NOAA space weather.
2. **Storage**: PostgreSQL + TimescaleDB hypertables, Redis cache + Celery broker.
3. **Compute**: SGP4 → altitude/inclination filters → k-d tree screening (5 km) → B-plane Pc (NASA CARA).
4. **API**: FastAPI REST under `/api/*`, WebSocket at `/ws/conjunctions`.
5. **Frontend**: Mission-console UI on a CesiumJS globe.

ML models **enhance** classical Pc — they never replace it. Operational maneuver threshold: **Pc ≈ 1e-4**.

Full diagram, DB schema, and algorithm notes in [`ARCHITECTURE.md`](ARCHITECTURE.md). Roadmap in [`PLAN.md`](PLAN.md).

---

## API surface

| Method | Path                          | Purpose                                          |
| ------ | ----------------------------- | ------------------------------------------------ |
| GET    | `/health`                     | Liveness probe                                   |
| GET    | `/api/satellites`             | Paginated catalog with regime / perigee / apogee |
| GET    | `/api/conjunctions`           | Upcoming conjunctions sorted by Pc               |
| GET    | `/api/conjunctions/{id}`      | Conjunction detail + CDM history                 |
| GET    | `/api/ml/compare/{id}`        | Classical vs. ML Pc + confidence                 |
| POST   | `/api/propagate`              | SGP4 propagation for a selection                 |
| GET    | `/api/positions`              | Single-epoch geodetic snapshot of full catalog   |
| GET/POST/PUT/DELETE | `/api/alerts`     | Alert configuration CRUD                         |
| WS     | `/ws/conjunctions`            | Push updates on new conjunctions                 |

Interactive schema: <http://localhost:8000/docs>.

---

## Testing

```bash
# Backend (pytest + async)
cd backend && pytest

# Single test
pytest tests/test_screening.py -k test_kdtree_finds_close_pair

# Type check + production build (frontend)
cd ../frontend && npx tsc --noEmit && npm run build
```

CI (GitHub Actions) runs the same suite on every push and PR.

---

## Deployment

| Component | Target                                    |
| --------- | ----------------------------------------- |
| API       | Fly.io (`backend/fly.toml`)               |
| Worker    | Fly.io process group (same app)           |
| Beat      | Fly.io process group (same app)           |
| Postgres  | Neon                                      |
| Redis     | Upstash                                   |
| Frontend  | Vercel (`frontend/vercel.json`)           |

```bash
cd backend
flyctl launch --no-deploy
flyctl secrets set \
  DATABASE_URL=... \
  REDIS_URL=... \
  CELERY_BROKER_URL=... \
  CELERY_RESULT_BACKEND=... \
  SPACETRACK_USERNAME=... \
  SPACETRACK_PASSWORD=... \
  RESEND_API_KEY=...
flyctl deploy

cd ../frontend
vercel --prod
```

---

## Configuration reference

All settings are read from environment variables (or a local `.env`). Sensible defaults exist for development; the table below highlights what you'll likely need to set.

| Variable                | Required        | Purpose                                          |
| ----------------------- | --------------- | ------------------------------------------------ |
| `DATABASE_URL`          | yes (prod)      | `postgresql+asyncpg://…` connection string       |
| `REDIS_URL`             | yes (prod)      | Cache + Celery broker                            |
| `CELERY_BROKER_URL`     | yes (prod)      | Celery broker (typically same as `REDIS_URL`)    |
| `CELERY_RESULT_BACKEND` | yes (prod)      | Celery results store                             |
| `SPACETRACK_USERNAME`   | yes (real data) | Space-Track.org account                          |
| `SPACETRACK_PASSWORD`   | yes (real data) | Space-Track.org account                          |
| `RESEND_API_KEY`        | optional        | Email alerts via Resend HTTPS API                |
| `SMTP_HOST` … `SMTP_*`  | optional        | Fallback SMTP if Resend not configured           |
| `SLACK_WEBHOOK_URL`     | optional        | Default Slack channel for alerts                 |
| `DISCORD_WEBHOOK_URL`   | optional        | Default Discord channel for alerts               |

See [`.env.example`](.env.example) for the full template.

---

## Troubleshooting

| Symptom                                                        | Likely cause / fix                                                                                  |
| -------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `TimeoutError` from asyncpg shortly after idle periods         | Neon kills idle connections. `pool_pre_ping=True` + `pool_recycle=300` already configured.          |
| API returns 200 but globe is empty                             | Catalog not yet ingested — run `fetch_spacetrack_catalog.apply()` or wait for the 03:30 UTC beat.   |
| Confirmation email never arrives                               | Resend free tier delivers **only to the verified account email**, lowercase. Verify a domain to relax. |
| `xgboost` import fails on macOS                                | `brew install libomp`.                                                                              |
| `alembic upgrade head` says `relation … already exists`        | Drop the dev DB volume: `docker compose down -v && docker compose up -d postgres`.                  |

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for branching, PR conventions, coding standards, and how to run the test suite locally.

All contributors are expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Security

Found a vulnerability? Please **don't** open a public issue — follow the responsible-disclosure process in [`SECURITY.md`](SECURITY.md).

---

## License

MIT — see [`LICENSE`](LICENSE).
