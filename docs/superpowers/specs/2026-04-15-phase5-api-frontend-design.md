# Phase 5: API Routes + Frontend Dashboard — Design Spec

## Goal
Get Collider running locally as a demo-ready app. All 4 backend computation layers (ingestion, SGP4, Pc, ML) are done. This phase wires them to a REST API and React+CesiumJS frontend.

## Approach
Vertical slices — each slice delivers one working API route + its frontend component.

## Slice Order
1. **Conjunctions** — API (satellites + conjunctions) + Conjunction Timeline UI
2. **Globe** — Propagation API + CesiumJS 3D Globe
3. **ML Insights** — ML compare API + Pc comparison panel
4. **Alerts** — Alert CRUD API + Alert config UI + WebSocket

---

## API Routes

All routes under `/api`, async SQLAlchemy sessions via FastAPI dependency injection.

### GET /api/satellites
- Query params: `regime` (LEO/MEO/GEO), `search` (name/NORAD), `limit` (default 100), `offset`
- Returns: paginated `SatelliteResponse[]` with orbital summary
- Source: `satellites` + latest `orbital_elements` join

### GET /api/conjunctions
- Query params: `min_pc` (float), `hours_ahead` (int, default 72), `limit` (default 50)
- Returns: `ConjunctionResponse[]` sorted by Pc desc
- Source: `conjunctions` table, joined with satellite names

### GET /api/conjunctions/{id}
- Returns: full conjunction detail — geometry, both objects, Pc classical + ML, CDM history
- Source: `conjunctions` + `cdm_history` + `satellites`

### POST /api/propagate
- Body: `{norad_ids: int[], duration_hours: float, step_minutes: float}`
- Returns: `{norad_id: int, positions: [{epoch, x, y, z, lat, lon, alt}]}[]`
- Calls: `propagate_catalog()` from propagation engine

### GET /api/ml/compare/{conjunction_id}
- Returns: `{pc_classical, pc_ml, confidence, risk_label, feature_importances: {name: value}[]}`
- Source: conjunctions table + MLInferenceEngine re-run for feature importances

### CRUD /api/alerts
- GET: list alert configs for user
- POST: create new alert config `{satellite_norad_id?, min_pc_threshold, channels: string[]}`
- PUT /{id}: update config
- DELETE /{id}: remove config
- Source: `alert_configs` table

### WS /ws/conjunctions
- On connect: send latest 10 conjunctions
- On screening task completion: push new/updated conjunctions
- Uses Redis pub/sub as broker between Celery worker and WebSocket

---

## Frontend Architecture

### Stack
- React 18 + TypeScript (Vite)
- Zustand (global state)
- TanStack React Query (data fetching)
- Resium (CesiumJS React wrapper)
- Recharts (charts)
- Tailwind CSS (dark space theme)

### Layout
```
Header (logo, search, alert bell, connection status)
├── Left Panel: ConjunctionTimeline (scrollable, sorted by Pc)
└── Right Panel:
    ├── Top: GlobeView (CesiumJS, takes ~60% height)
    └── Bottom: EventDetailPanel (selected conjunction details)
```

### State (Zustand)
```typescript
interface ColliderStore {
  selectedConjunctionId: number | null
  selectConjunction: (id: number) => void
  sidebarCollapsed: boolean
  toggleSidebar: () => void
}
```
React Query handles all server state (satellites, conjunctions, propagation data).

### Components

**ConjunctionTimeline**
- Fetches GET /api/conjunctions every 30s (React Query polling)
- Cards show: primary + secondary object names, Pc (color-coded), TCA countdown, miss distance
- Click selects → updates globe + detail panel

**GlobeView**
- CesiumJS via Resium, Cesium Ion token from env
- On mount: fetch top-risk satellites via /api/propagate
- Selected conjunction: highlight both orbits, draw miss-distance line at TCA
- Color coding: green (Pc < 1e-6), yellow (1e-6 to 1e-4), red (> 1e-4)

**EventDetailPanel**
- Fetches GET /api/conjunctions/{id} + GET /api/ml/compare/{id}
- Shows: orbital geometry, miss distance, relative velocity
- Recharts bar/line chart: ML vs Classical Pc with confidence interval
- "Configure Alert" button opens AlertConfigForm

**AlertConfigForm**
- Modal form, CRUD against /api/alerts
- Fields: threshold (Pc), notification channels (email, slack), watched satellites

**Header**
- Logo + title
- Satellite search (typeahead against /api/satellites?search=)
- Alert bell with unread count
- WebSocket connection indicator (green/red dot)

### Cesium Ion Token
- Stored in `frontend/.env` as `VITE_CESIUM_ION_TOKEN`
- Loaded via `Ion.defaultAccessToken` on app init

### Dark Theme
Tailwind config with custom palette: deep navy background, bright accent for risk levels.

---

## Infrastructure (local)
- `docker-compose up` starts PostgreSQL + Redis
- `cd backend && uvicorn src.main:app --reload` starts API
- `cd frontend && npm run dev` starts Vite dev server (proxied to API)
- Vite proxy: `/api/*` and `/ws/*` → `http://localhost:8000`

## Not in Scope
- Authentication / user management
- Production deployment (Phase 6)
- Mobile responsive design
- Real-time TLE ingestion during demo (pre-loaded data is fine)
