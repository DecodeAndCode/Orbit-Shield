# Collider — Architecture Document

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     DATA SOURCES                            │
│  Space-Track.org │ CelesTrak │ NOAA Weather │ LeoLabs      │
└────────┬──────────────┬───────────┬──────────────┬──────────┘
         │              │           │              │
         ▼              ▼           ▼              ▼
┌─────────────────────────────────────────────────────────────┐
│              DATA INGESTION LAYER (Celery Workers)          │
│  TLE Fetcher │ CDM Parser │ Weather Collector │ SOCRATES    │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│              STORAGE LAYER                                  │
│  PostgreSQL (catalog, CDMs) │ TimescaleDB (time-series)     │
│  Redis (latest states, cache) │ S3/MinIO (ML artifacts)    │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│              COMPUTATION ENGINE                             │
│  SGP4 Propagator → Conjunction Screening → Pc Computation  │
│       │                                        │           │
│       └──── ML Orbit Correction ───────────────┘           │
│       └──── ML Covariance Estimation ──────────┘           │
│       └──── ML Conjunction Evolution Prediction ┘          │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│              API LAYER (FastAPI)                             │
│  REST endpoints │ WebSocket streams │ GraphQL (optional)    │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│              FRONTEND (React + CesiumJS)                    │
│  3D Globe │ Conjunction Dashboard │ Alert Config │ ML Panel │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│              ALERT SYSTEM                                   │
│  Email │ Slack/Discord │ SMS (Twilio) │ Webhook             │
└─────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Language (Backend)** | Python | Dominant in astrodynamics, best library support (sgp4, astropy, poliastro) |
| **Language (Frontend)** | TypeScript + React | Vite scaffolded (`npm create vite@latest frontend -- --template react-ts`) |
| **Backend Framework** | FastAPI | Async, fast, auto-generated OpenAPI docs |
| **Database** | PostgreSQL + TimescaleDB extension | Relational for catalog, time-series for orbital history |
| **Cache** | Redis | Latest TLE states, active conjunction cache |
| **Task Queue** | Celery + Redis broker | Background ingestion, propagation batch jobs |
| **3D Visualization** | CesiumJS + Resium (React wrapper) | Industry-standard for satellite orbit visualization |
| **Charts** | Recharts / D3.js | Pc trends, conjunction timelines |
| **ML Framework** | PyTorch | Neural ODEs (torchdiffeq), PINNs, Transformer models |
| **ML Baselines** | XGBoost, LightGBM, scikit-learn | Gradient boosting baselines, feature engineering |
| **Experiment Tracking** | Weights & Biases (wandb) | Model versioning, hyperparameter sweeps |
| **JS Orbital** | satellite.js | Client-side SGP4 for lightweight browser visualization |

---

## Directory Structure (Proposed Monorepo)

```
collider/
├── CLAUDE.md                    # Claude Code project context
├── PLAN.md                      # This plan document
├── ARCHITECTURE.md              # This file
├── README.md
├── docker-compose.yml           # PostgreSQL, Redis, Celery, backend
│
├── backend/
│   ├── CLAUDE.md                # Backend-specific Claude context
│   ├── pyproject.toml
│   ├── src/
│   │   ├── main.py              # FastAPI app entry
│   │   ├── config.py            # Settings, env vars
│   │   ├── db/
│   │   │   ├── models.py        # SQLAlchemy ORM models
│   │   │   ├── schemas.py       # Pydantic request/response schemas
│   │   │   └── session.py       # DB connection
│   │   ├── ingestion/
│   │   │   ├── spacetrack.py    # Space-Track.org API client
│   │   │   ├── celestrak.py     # CelesTrak data fetcher
│   │   │   ├── socrates.py      # SOCRATES conjunction parser
│   │   │   ├── weather.py       # NOAA space weather fetcher
│   │   │   └── tasks.py         # Celery task definitions
│   │   ├── propagation/
│   │   │   ├── sgp4_engine.py   # SGP4 batch propagation
│   │   │   ├── screening.py     # Conjunction screening (k-d tree)
│   │   │   └── probability.py   # Classical Pc computation (B-plane)
│   │   ├── ml/
│   │   │   ├── features.py      # Feature engineering pipeline
│   │   │   ├── conjunction_evolution.py  # ML Task 1: CDM sequence prediction
│   │   │   ├── orbit_correction.py      # ML Task 2: Neural ODE / PINN
│   │   │   ├── covariance_estimation.py # ML Task 3: TLE → covariance
│   │   │   └── training/
│   │   │       ├── train.py
│   │   │       └── evaluate.py
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── catalog.py   # GET /satellites, GET /satellites/{norad_id}
│   │   │   │   ├── conjunctions.py  # GET /conjunctions, GET /conjunctions/{id}
│   │   │   │   ├── propagation.py   # POST /propagate
│   │   │   │   └── alerts.py       # Alert config CRUD
│   │   │   └── websocket.py    # Real-time conjunction updates
│   │   └── alerts/
│   │       ├── engine.py        # Threshold evaluation
│   │       ├── email.py
│   │       └── slack.py
│   └── tests/
│
├── frontend/
│   ├── CLAUDE.md                # Frontend-specific Claude context
│   ├── package.json
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── Globe/           # CesiumJS 3D earth + orbits
│   │   │   ├── ConjunctionTimeline/
│   │   │   ├── EventDetail/     # Deep-dive: miss distance, Pc evolution
│   │   │   ├── AlertConfig/
│   │   │   └── MLInsights/      # ML vs classical Pc comparison
│   │   ├── hooks/
│   │   ├── services/            # API client (axios)
│   │   └── stores/              # State management (Zustand or React Context)
│   └── public/
│
├── ml/
│   ├── notebooks/               # Jupyter exploration
│   ├── data/                    # Processed datasets (gitignored)
│   └── models/                  # Saved model artifacts (gitignored)
│
└── docs/
    └── CONTEXT.md               # Project background & decisions from planning
```

---

## Database Schema (Core Tables)

```sql
-- Satellite catalog
CREATE TABLE satellites (
    norad_id INTEGER PRIMARY KEY,
    name VARCHAR(255),
    object_type VARCHAR(50),    -- 'PAYLOAD', 'ROCKET BODY', 'DEBRIS'
    country VARCHAR(100),
    launch_date DATE,
    decay_date DATE,
    rcs_size VARCHAR(20),       -- radar cross-section category
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- TLE/OMM orbital elements (time-series)
CREATE TABLE orbital_elements (
    id BIGSERIAL PRIMARY KEY,
    norad_id INTEGER REFERENCES satellites(norad_id),
    epoch TIMESTAMPTZ NOT NULL,
    tle_line1 TEXT,
    tle_line2 TEXT,
    mean_motion DOUBLE PRECISION,
    eccentricity DOUBLE PRECISION,
    inclination DOUBLE PRECISION,
    raan DOUBLE PRECISION,       -- right ascension of ascending node
    arg_perigee DOUBLE PRECISION,
    mean_anomaly DOUBLE PRECISION,
    bstar DOUBLE PRECISION,      -- drag term
    fetched_at TIMESTAMPTZ DEFAULT NOW()
);

-- Conjunction events
CREATE TABLE conjunctions (
    id BIGSERIAL PRIMARY KEY,
    primary_norad_id INTEGER REFERENCES satellites(norad_id),
    secondary_norad_id INTEGER REFERENCES satellites(norad_id),
    tca TIMESTAMPTZ NOT NULL,                 -- time of closest approach
    miss_distance_km DOUBLE PRECISION,
    relative_velocity_kms DOUBLE PRECISION,
    pc_classical DOUBLE PRECISION,            -- classical probability of collision
    pc_ml DOUBLE PRECISION,                   -- ML-enhanced Pc
    screening_source VARCHAR(50),             -- 'SOCRATES', 'COMPUTED', 'CDM'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- CDM history (for ML training)
CREATE TABLE cdm_history (
    id BIGSERIAL PRIMARY KEY,
    conjunction_id BIGINT REFERENCES conjunctions(id),
    cdm_timestamp TIMESTAMPTZ,
    tca TIMESTAMPTZ,
    miss_distance_km DOUBLE PRECISION,
    pc DOUBLE PRECISION,
    primary_covariance JSONB,    -- 6x6 covariance matrix
    secondary_covariance JSONB,
    raw_cdm JSONB                -- full CDM data
);

-- Alerts configuration
CREATE TABLE alert_configs (
    id SERIAL PRIMARY KEY,
    watched_norad_ids INTEGER[],
    pc_threshold DOUBLE PRECISION DEFAULT 1e-4,
    notification_channels JSONB,  -- {"email": "...", "slack_webhook": "..."}
    enabled BOOLEAN DEFAULT TRUE
);
```

---

## Key API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/satellites` | List catalog (filterable by type, orbit regime) |
| GET | `/api/satellites/{norad_id}` | Satellite detail + latest TLE |
| POST | `/api/propagate` | Propagate satellite(s) for time range |
| GET | `/api/conjunctions` | List conjunctions (sortable by Pc, TCA) |
| GET | `/api/conjunctions/{id}` | Conjunction detail + CDM history |
| WS | `/ws/conjunctions` | Real-time conjunction updates stream |
| CRUD | `/api/alerts` | Alert configuration management |
| GET | `/api/ml/compare/{conjunction_id}` | Classical vs. ML Pc comparison |

---

## Key Algorithms

### Conjunction Screening (O(n log n) via spatial indexing)
```python
from scipy.spatial import cKDTree

positions = propagate_all_satellites(catalog, t)  # shape: (N, 3)
tree = cKDTree(positions)
pairs = tree.query_pairs(r=5.0)  # 5 km screening radius
```

Pre-filters before spatial search:
1. Perigee/Apogee altitude overlap check
2. Orbital plane (inclination) filter
3. k-d tree at each time step
4. Numerical root-finding for exact TCA on candidate pairs

### Classical Pc Computation (B-plane method)
1. Project encounter into B-plane (perpendicular to relative velocity)
2. Combine covariance ellipsoids into joint 2D covariance
3. Integrate 2D Gaussian over circular hard-body radius

### Covariance Estimation (TLE-derived)
Compare sequential TLEs for same object → empirical position uncertainty.
CDMs from Space-Track provide proper covariances for specific events.

---

## Dependencies

```bash
# Core orbital mechanics
sgp4 astropy skyfield poliastro

# Data & ML
numpy scipy pandas scikit-learn
torch torchvision torchdiffeq
xgboost lightgbm wandb

# Backend
fastapi uvicorn sqlalchemy psycopg2-binary
celery redis aiohttp httpx

# Visualization
plotly matplotlib

# Frontend
react react-dom typescript vite
cesium resium recharts three @react-three/fiber
axios socket.io-client
```

---

## Reference Projects
- `KeepTrack` — Open-source space visualization (keeptrack.space)
- `python-sgp4` — Official SGP4 by Brandon Rhodes
- `poliastro` — Astrodynamics library with conjunction tools
- `satellite.js` — JavaScript SGP4 for browser
- `Orbital Object Toolkit (ootk)` — TypeScript satellite toolkit
- `space-track-python` — Python wrapper for Space-Track API
- `Detour` (TreeHacks 2026) — Multi-agentic collision avoidance on NVIDIA DGX Spark
