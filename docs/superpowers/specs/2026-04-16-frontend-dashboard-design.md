# Collider Frontend Dashboard — Design Spec
_2026-04-16_

## Overview

Globe-first React+TypeScript dashboard consuming the Phase 5 FastAPI backend. Left side panel for conjunction data. Three routes. Zustand state. 30s polling.

## Layout

- **Full-screen CesiumJS globe** as the base layer on `/`
- **Left side panel** (toggleable, ~320px) — conjunction list sorted by Pc
- **Top nav bar** — logo, route links, live indicator, critical count badge
- Panel open/close toggled via a chevron button; globe resizes to fill remaining width

## Routes

| Route | Component | Description |
|-------|-----------|-------------|
| `/` | `GlobePage` | CesiumJS globe + ConjunctionPanel |
| `/satellites` | `SatellitesPage` | Searchable/paginated catalog table |
| `/alerts` | `AlertsPage` | CRUD table for AlertConfig |

## Components

### `GlobePage`
- Mounts `<Viewer>` (Resium) full-screen
- Renders satellites as `<PointPrimitiveCollection>` (color by regime)
- Renders selected conjunction pair as two `<Polyline>` entities (red dashed at TCA)
- Clicking conjunction in panel → `viewer.flyTo()` to midpoint
- Clicking satellite entity → detail `<Popover>` with NORAD, epoch, regime

### `ConjunctionPanel`
- Left sidebar, `position: fixed`, `z-index` above globe
- List of `ConjunctionCard` items from `useConjunctionStore`
- Color-coded border: red ≥ 1e-4, yellow ≥ 1e-5, blue below
- Each card: primary/secondary NORAD+name, Pc (classical), Pc (ML, if available), TCA countdown
- Clicking card → sets `selectedConjunctionId` in store → globe reacts

### `ConjunctionDetail` (inline expansion in panel)
- Expands below clicked card
- Miss distance, relative velocity
- Recharts `BarChart`: classical Pc vs ML Pc side-by-side
- "Compare" button → `GET /api/ml/compare/{id}`

### `SatellitesPage`
- Search input → `GET /api/satellites?search=…`
- Pagination controls
- Table: NORAD ID, name, regime, epoch, inclination, altitude

### `AlertsPage`
- Table of existing alerts from `GET /api/alerts`
- "New Alert" button → inline form row
- Edit/delete per row
- Fields: pc_threshold, notification_channels (JSON display), enabled toggle

## State (Zustand)

```ts
// useConjunctionStore
conjunctions: ConjunctionSummary[]
selectedId: number | null
lastFetched: Date | null
fetch(): Promise<void>           // GET /api/conjunctions
fetchDetail(id): Promise<void>   // GET /api/conjunctions/{id}

// useSatelliteStore
satellites: Satellite[]
total: number
page: number
search: string
fetch(): Promise<void>           // GET /api/satellites

// useAlertStore
alerts: AlertConfig[]
fetch(): Promise<void>
create(body): Promise<void>
update(id, body): Promise<void>
remove(id): Promise<void>
```

## API Client

`src/api/client.ts` — typed fetch wrapper with base URL from `VITE_API_BASE_URL` env var (default `http://localhost:8000`). One function per endpoint, returns typed response or throws.

## Data Polling

`usePolling(store.fetch, 30_000)` custom hook — `setInterval` on mount, clears on unmount. Used in `GlobePage` for conjunctions, `SatellitesPage` for satellites.

## Dependencies to Install

```
react-router-dom
zustand
axios (or native fetch — use fetch, no extra dep)
recharts
@types/recharts
cesium
resium
```

CesiumJS requires `vite-plugin-cesium` for asset copying.

## Styling

CSS modules per component. Dark space theme extending existing `index.css`. No UI component library. Color tokens:
- `--critical: #f85149` (Pc ≥ 1e-4)
- `--warning: #e3b341` (Pc ≥ 1e-5)
- `--nominal: #388bfd` (Pc < 1e-5)
- `--bg-base: #0d1117`
- `--bg-surface: #161b22`
- `--border: #30363d`

## Out of Scope (Phase 5)

- WebSocket real-time push (WS backend is a stub)
- Email/Slack notification delivery
- Propagation UI (`/propagate` form) — API exists, no UI needed yet
- Authentication
