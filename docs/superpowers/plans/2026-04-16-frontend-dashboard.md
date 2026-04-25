# Collider Frontend Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Collider React+TypeScript frontend dashboard — globe-first layout with left conjunction panel, satellites catalog, and alerts CRUD — consuming the Phase 5 FastAPI backend.

**Architecture:** Globe-first single-page app (React Router v6). Full-screen CesiumJS globe on `/`, toggleable left panel listing conjunctions sorted by Pc. Two additional routes: `/satellites` (paginated catalog table) and `/alerts` (alert config CRUD). Zustand manages all async state; a typed fetch client wraps every API call; a `usePolling` hook drives 30s refresh on all stores.

**Tech Stack:** React 19 + TypeScript, Vite 7, React Router v6, Zustand, CesiumJS + Resium, Recharts, vite-plugin-cesium, Vitest + @testing-library/react

---

## File Map

```
frontend/
  vite.config.ts                      MODIFY — add vite-plugin-cesium
  src/
    index.css                         MODIFY — add CSS custom properties (dark theme tokens)
    main.tsx                          MODIFY — wrap with BrowserRouter
    App.tsx                           MODIFY — define 3 routes
    api/
      types.ts                        CREATE — all API response/request types
      client.ts                       CREATE — typed fetch wrapper (base URL from env)
    stores/
      useConjunctionStore.ts          CREATE — conjunctions list + selected ID + fetch
      useSatelliteStore.ts            CREATE — satellites list + pagination + search + fetch
      useAlertStore.ts                CREATE — alerts CRUD
    hooks/
      usePolling.ts                   CREATE — setInterval wrapper for store.fetch
    components/
      Nav/
        Nav.tsx                       CREATE — top navbar (links + live badge + critical count)
        Nav.module.css                CREATE
      ConjunctionPanel/
        ConjunctionPanel.tsx          CREATE — fixed left sidebar, list of cards
        ConjunctionPanel.module.css   CREATE
        ConjunctionCard.tsx           CREATE — single conjunction row with color-coded border
        ConjunctionDetail.tsx         CREATE — expanded view with Recharts Pc comparison
      Globe/
        GlobePage.tsx                 CREATE — CesiumJS viewer + panel + polling
        GlobePage.module.css          CREATE
    pages/
      SatellitesPage/
        SatellitesPage.tsx            CREATE — table + search + pagination
        SatellitesPage.module.css     CREATE
      AlertsPage/
        AlertsPage.tsx                CREATE — CRUD table for AlertConfig
        AlertsPage.module.css         CREATE
    test/
      setup.ts                        CREATE — vitest setup (jsdom)
      api.client.test.ts              CREATE — client smoke tests
      stores.test.ts                  CREATE — store smoke tests
```

---

## Task 1: Install Dependencies and Configure Vite

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Install all required packages**

```bash
cd frontend
npm install react-router-dom zustand recharts cesium resium
npm install -D vite-plugin-cesium vitest @vitest/coverage-v8 @testing-library/react @testing-library/jest-dom jsdom @types/recharts
```

Expected output: packages installed, no peer dep errors (cesium and resium must be compatible — cesium@1.x works with resium@1.x).

- [ ] **Step 2: Update vite.config.ts**

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import cesium from 'vite-plugin-cesium'

export default defineConfig({
  plugins: [react(), cesium()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
})
```

- [ ] **Step 3: Create test setup file**

Create `frontend/src/test/setup.ts`:
```ts
import '@testing-library/jest-dom'
```

- [ ] **Step 4: Add CSS tokens to index.css**

Prepend to `frontend/src/index.css`:
```css
:root {
  --critical: #f85149;
  --warning: #e3b341;
  --nominal: #388bfd;
  --bg-base: #0d1117;
  --bg-surface: #161b22;
  --bg-raised: #21262d;
  --border: #30363d;
  --text-primary: #e6edf3;
  --text-secondary: #8b949e;
  --accent: #58a6ff;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: var(--bg-base);
  color: var(--text-primary);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 14px;
  height: 100vh;
  overflow: hidden;
}

#root { height: 100vh; display: flex; flex-direction: column; }
```

- [ ] **Step 5: Create .env file for API base URL**

Create `frontend/.env`:
```
VITE_API_BASE_URL=http://localhost:8000
```

- [ ] **Step 6: Verify Vite starts without errors**

```bash
npm run dev
```
Expected: server starts at http://localhost:5173, no TypeScript errors in console.

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/vite.config.ts frontend/src/index.css frontend/src/test/setup.ts frontend/.env
git commit -m "feat(frontend): install deps, configure Vite+Cesium, add CSS tokens"
```

---

## Task 2: API Types and Typed Fetch Client

**Files:**
- Create: `frontend/src/api/types.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/test/api.client.test.ts`

- [ ] **Step 1: Write failing test**

Create `frontend/src/test/api.client.test.ts`:
```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'

describe('apiClient', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  it('getSatellites calls correct URL with params', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [], total: 0, limit: 50 }),
    } as Response)

    const { getSatellites } = await import('../api/client')
    await getSatellites({ page: 1, limit: 50 })

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/satellites?page=1&limit=50'),
      expect.any(Object)
    )
  })

  it('throws on non-ok response', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: 'Not Found',
    } as Response)

    const { getConjunctionDetail } = await import('../api/client')
    await expect(getConjunctionDetail(999)).rejects.toThrow('404')
  })
})
```

- [ ] **Step 2: Run test — expect FAIL (module not found)**

```bash
npx vitest run src/test/api.client.test.ts
```
Expected: FAIL — `Cannot find module '../api/client'`

- [ ] **Step 3: Create API types**

Create `frontend/src/api/types.ts`:
```ts
export interface Satellite {
  norad_id: number
  name: string
  international_designator: string | null
  object_type: string | null
  orbital_regime: string | null
  inclination_deg: number | null
  altitude_km: number | null
  epoch: string | null
}

export interface SatellitesResponse {
  items: Satellite[]
  total: number
  limit: number
}

export interface ConjunctionSummary {
  id: number
  primary_norad_id: number
  secondary_norad_id: number
  primary_name: string | null
  secondary_name: string | null
  tca: string
  miss_distance_km: number
  pc_classical: number | null
  pc_ml: number | null
  relative_velocity_kms: number | null
}

export interface ConjunctionDetail extends ConjunctionSummary {
  relative_position_km: [number, number, number] | null
  relative_velocity_kms_vec: [number, number, number] | null
}

export interface MLCompareResponse {
  conjunction_id: number
  pc_classical: number | null
  pc_ml: number | null
  ml_available: boolean
  model_version: string | null
}

export interface AlertConfig {
  id: number
  watched_norad_ids: number[] | null
  pc_threshold: number
  notification_channels: Record<string, string> | null
  enabled: boolean
}

export interface AlertConfigCreate {
  watched_norad_ids?: number[]
  pc_threshold?: number
  notification_channels?: Record<string, string>
  enabled?: boolean
}
```

- [ ] **Step 4: Create API client**

Create `frontend/src/api/client.ts`:
```ts
import type {
  Satellite, SatellitesResponse,
  ConjunctionSummary, ConjunctionDetail,
  MLCompareResponse,
  AlertConfig, AlertConfigCreate,
} from './types'

const BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export function getSatellites(params: { page?: number; limit?: number; search?: string; regime?: string }) {
  const q = new URLSearchParams()
  if (params.page != null) q.set('page', String(params.page))
  if (params.limit != null) q.set('limit', String(params.limit))
  if (params.search) q.set('search', params.search)
  if (params.regime) q.set('regime', params.regime)
  return request<SatellitesResponse>(`/api/satellites?${q}`)
}

export function getConjunctions() {
  return request<ConjunctionSummary[]>('/api/conjunctions')
}

export function getConjunctionDetail(id: number) {
  return request<ConjunctionDetail>(`/api/conjunctions/${id}`)
}

export function getMLCompare(id: number) {
  return request<MLCompareResponse>(`/api/ml/compare/${id}`)
}

export function getAlerts() {
  return request<AlertConfig[]>('/api/alerts')
}

export function createAlert(body: AlertConfigCreate) {
  return request<AlertConfig>('/api/alerts', { method: 'POST', body: JSON.stringify(body) })
}

export function updateAlert(id: number, body: AlertConfigCreate) {
  return request<AlertConfig>(`/api/alerts/${id}`, { method: 'PUT', body: JSON.stringify(body) })
}

export function deleteAlert(id: number) {
  return fetch(`${BASE}/api/alerts/${id}`, { method: 'DELETE' })
}
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
npx vitest run src/test/api.client.test.ts
```
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/ frontend/src/test/api.client.test.ts
git commit -m "feat(frontend): typed API client and response types"
```

---

## Task 3: Zustand Stores

**Files:**
- Create: `frontend/src/stores/useConjunctionStore.ts`
- Create: `frontend/src/stores/useSatelliteStore.ts`
- Create: `frontend/src/stores/useAlertStore.ts`
- Create: `frontend/src/test/stores.test.ts`

- [ ] **Step 1: Write failing store tests**

Create `frontend/src/test/stores.test.ts`:
```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../api/client', () => ({
  getConjunctions: vi.fn().mockResolvedValue([
    { id: 1, primary_norad_id: 25544, secondary_norad_id: 99001,
      primary_name: 'ISS', secondary_name: 'SL-1', tca: '2026-04-16T10:00:00Z',
      miss_distance_km: 0.8, pc_classical: 3.2e-4, pc_ml: null, relative_velocity_kms: null }
  ]),
  getSatellites: vi.fn().mockResolvedValue({ items: [], total: 0, limit: 50 }),
  getAlerts: vi.fn().mockResolvedValue([]),
}))

describe('useConjunctionStore', () => {
  beforeEach(() => vi.clearAllMocks())

  it('fetch populates conjunctions', async () => {
    const { useConjunctionStore } = await import('../stores/useConjunctionStore')
    const store = useConjunctionStore.getState()
    await store.fetch()
    expect(useConjunctionStore.getState().conjunctions).toHaveLength(1)
    expect(useConjunctionStore.getState().conjunctions[0].id).toBe(1)
  })

  it('setSelected updates selectedId', async () => {
    const { useConjunctionStore } = await import('../stores/useConjunctionStore')
    useConjunctionStore.getState().setSelected(42)
    expect(useConjunctionStore.getState().selectedId).toBe(42)
  })
})

describe('useSatelliteStore', () => {
  it('fetch sets satellites to empty array', async () => {
    const { useSatelliteStore } = await import('../stores/useSatelliteStore')
    await useSatelliteStore.getState().fetch()
    expect(useSatelliteStore.getState().satellites).toEqual([])
    expect(useSatelliteStore.getState().total).toBe(0)
  })
})
```

- [ ] **Step 2: Run — expect FAIL**

```bash
npx vitest run src/test/stores.test.ts
```
Expected: FAIL — modules not found

- [ ] **Step 3: Create conjunction store**

Create `frontend/src/stores/useConjunctionStore.ts`:
```ts
import { create } from 'zustand'
import { getConjunctions, getConjunctionDetail } from '../api/client'
import type { ConjunctionSummary, ConjunctionDetail } from '../api/types'

interface ConjunctionStore {
  conjunctions: ConjunctionSummary[]
  selectedId: number | null
  detail: ConjunctionDetail | null
  loading: boolean
  error: string | null
  fetch: () => Promise<void>
  setSelected: (id: number | null) => void
  fetchDetail: (id: number) => Promise<void>
}

export const useConjunctionStore = create<ConjunctionStore>((set) => ({
  conjunctions: [],
  selectedId: null,
  detail: null,
  loading: false,
  error: null,
  fetch: async () => {
    set({ loading: true, error: null })
    try {
      const conjunctions = await getConjunctions()
      conjunctions.sort((a, b) => (b.pc_classical ?? 0) - (a.pc_classical ?? 0))
      set({ conjunctions, loading: false })
    } catch (e) {
      set({ error: String(e), loading: false })
    }
  },
  setSelected: (id) => set({ selectedId: id, detail: null }),
  fetchDetail: async (id) => {
    try {
      const detail = await getConjunctionDetail(id)
      set({ detail })
    } catch (e) {
      set({ error: String(e) })
    }
  },
}))
```

- [ ] **Step 4: Create satellite store**

Create `frontend/src/stores/useSatelliteStore.ts`:
```ts
import { create } from 'zustand'
import { getSatellites } from '../api/client'
import type { Satellite } from '../api/types'

interface SatelliteStore {
  satellites: Satellite[]
  total: number
  page: number
  limit: number
  search: string
  loading: boolean
  error: string | null
  fetch: () => Promise<void>
  setSearch: (search: string) => void
  setPage: (page: number) => void
}

export const useSatelliteStore = create<SatelliteStore>((set, get) => ({
  satellites: [],
  total: 0,
  page: 1,
  limit: 50,
  search: '',
  loading: false,
  error: null,
  fetch: async () => {
    const { page, limit, search } = get()
    set({ loading: true, error: null })
    try {
      const res = await getSatellites({ page, limit, search })
      set({ satellites: res.items, total: res.total, loading: false })
    } catch (e) {
      set({ error: String(e), loading: false })
    }
  },
  setSearch: (search) => set({ search, page: 1 }),
  setPage: (page) => set({ page }),
}))
```

- [ ] **Step 5: Create alert store**

Create `frontend/src/stores/useAlertStore.ts`:
```ts
import { create } from 'zustand'
import { getAlerts, createAlert, updateAlert, deleteAlert } from '../api/client'
import type { AlertConfig, AlertConfigCreate } from '../api/types'

interface AlertStore {
  alerts: AlertConfig[]
  loading: boolean
  error: string | null
  fetch: () => Promise<void>
  create: (body: AlertConfigCreate) => Promise<void>
  update: (id: number, body: AlertConfigCreate) => Promise<void>
  remove: (id: number) => Promise<void>
}

export const useAlertStore = create<AlertStore>((set, get) => ({
  alerts: [],
  loading: false,
  error: null,
  fetch: async () => {
    set({ loading: true, error: null })
    try {
      const alerts = await getAlerts()
      set({ alerts, loading: false })
    } catch (e) {
      set({ error: String(e), loading: false })
    }
  },
  create: async (body) => {
    await createAlert(body)
    await get().fetch()
  },
  update: async (id, body) => {
    await updateAlert(id, body)
    await get().fetch()
  },
  remove: async (id) => {
    await deleteAlert(id)
    await get().fetch()
  },
}))
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
npx vitest run src/test/stores.test.ts
```
Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
git add frontend/src/stores/ frontend/src/test/stores.test.ts
git commit -m "feat(frontend): Zustand stores for conjunctions, satellites, alerts"
```

---

## Task 4: usePolling Hook + Nav Component

**Files:**
- Create: `frontend/src/hooks/usePolling.ts`
- Create: `frontend/src/components/Nav/Nav.tsx`
- Create: `frontend/src/components/Nav/Nav.module.css`

- [ ] **Step 1: Create usePolling hook**

Create `frontend/src/hooks/usePolling.ts`:
```ts
import { useEffect, useRef } from 'react'

export function usePolling(fn: () => void, intervalMs: number) {
  const savedFn = useRef(fn)
  savedFn.current = fn

  useEffect(() => {
    savedFn.current()
    const id = setInterval(() => savedFn.current(), intervalMs)
    return () => clearInterval(id)
  }, [intervalMs])
}
```

- [ ] **Step 2: Create Nav component**

Create `frontend/src/components/Nav/Nav.tsx`:
```tsx
import { NavLink } from 'react-router-dom'
import { useConjunctionStore } from '../../stores/useConjunctionStore'
import styles from './Nav.module.css'

export function Nav() {
  const conjunctions = useConjunctionStore((s) => s.conjunctions)
  const critical = conjunctions.filter((c) => (c.pc_classical ?? 0) >= 1e-4).length

  return (
    <nav className={styles.nav}>
      <span className={styles.logo}>COLLIDER</span>
      <div className={styles.links}>
        <NavLink to="/" end className={({ isActive }) => isActive ? styles.active : ''}>Globe</NavLink>
        <NavLink to="/satellites" className={({ isActive }) => isActive ? styles.active : ''}>Satellites</NavLink>
        <NavLink to="/alerts" className={({ isActive }) => isActive ? styles.active : ''}>Alerts</NavLink>
      </div>
      <div className={styles.status}>
        <span className={styles.liveDot} />
        <span className={styles.liveLabel}>LIVE · 30s</span>
        {critical > 0 && (
          <span className={styles.criticalBadge}>{critical} CRITICAL</span>
        )}
      </div>
    </nav>
  )
}
```

- [ ] **Step 3: Create Nav CSS module**

Create `frontend/src/components/Nav/Nav.module.css`:
```css
.nav {
  height: 40px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 16px;
  gap: 24px;
  flex-shrink: 0;
  z-index: 100;
}
.logo {
  color: var(--accent);
  font-weight: 700;
  letter-spacing: 2px;
  font-size: 13px;
}
.links {
  display: flex;
  gap: 16px;
}
.links a {
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 13px;
}
.links a:hover { color: var(--text-primary); }
.active { color: var(--text-primary) !important; }
.status {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
}
.liveDot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #3fb950;
}
.liveLabel {
  color: var(--text-secondary);
  font-size: 11px;
}
.criticalBadge {
  background: color-mix(in srgb, var(--critical) 15%, transparent);
  color: var(--critical);
  border: 1px solid color-mix(in srgb, var(--critical) 40%, transparent);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/ frontend/src/components/Nav/
git commit -m "feat(frontend): usePolling hook and Nav component"
```

---

## Task 5: ConjunctionPanel and ConjunctionCard

**Files:**
- Create: `frontend/src/components/ConjunctionPanel/ConjunctionPanel.tsx`
- Create: `frontend/src/components/ConjunctionPanel/ConjunctionPanel.module.css`
- Create: `frontend/src/components/ConjunctionPanel/ConjunctionCard.tsx`

- [ ] **Step 1: Create ConjunctionCard**

Create `frontend/src/components/ConjunctionPanel/ConjunctionCard.tsx`:
```tsx
import type { ConjunctionSummary } from '../../api/types'
import styles from './ConjunctionPanel.module.css'

function pcColor(pc: number | null): string {
  if (pc == null) return 'var(--nominal)'
  if (pc >= 1e-4) return 'var(--critical)'
  if (pc >= 1e-5) return 'var(--warning)'
  return 'var(--nominal)'
}

function formatPc(pc: number | null): string {
  if (pc == null) return 'N/A'
  return pc.toExponential(1)
}

function tcaCountdown(tca: string): string {
  const diff = new Date(tca).getTime() - Date.now()
  if (diff < 0) return 'passed'
  const h = Math.floor(diff / 3_600_000)
  const m = Math.floor((diff % 3_600_000) / 60_000)
  return `${h}h ${m}m`
}

interface Props {
  conjunction: ConjunctionSummary
  selected: boolean
  onClick: () => void
}

export function ConjunctionCard({ conjunction: c, selected, onClick }: Props) {
  const color = pcColor(c.pc_classical)
  return (
    <div
      className={`${styles.card} ${selected ? styles.cardSelected : ''}`}
      style={{ borderLeftColor: color }}
      onClick={onClick}
    >
      <div className={styles.cardTitle}>
        {c.primary_name ?? c.primary_norad_id} × {c.secondary_name ?? c.secondary_norad_id}
      </div>
      <div className={styles.cardMeta}>
        <span style={{ color }}>Pc {formatPc(c.pc_classical)}</span>
        <span className={styles.tca}>TCA {tcaCountdown(c.tca)}</span>
      </div>
      {c.pc_ml != null && (
        <div className={styles.mlRow}>
          <span className={styles.mlLabel}>classical</span>
          <span className={styles.mlLabel} style={{ color: 'var(--accent)' }}>
            ML: {formatPc(c.pc_ml)}
          </span>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Create ConjunctionPanel**

Create `frontend/src/components/ConjunctionPanel/ConjunctionPanel.tsx`:
```tsx
import { useConjunctionStore } from '../../stores/useConjunctionStore'
import { ConjunctionCard } from './ConjunctionCard'
import { ConjunctionDetail } from './ConjunctionDetail'
import styles from './ConjunctionPanel.module.css'

interface Props {
  open: boolean
  onToggle: () => void
}

export function ConjunctionPanel({ open, onToggle }: Props) {
  const { conjunctions, selectedId, setSelected, loading } = useConjunctionStore()

  return (
    <aside className={`${styles.panel} ${open ? styles.panelOpen : styles.panelClosed}`}>
      <div className={styles.header}>
        <span className={styles.headerLabel}>
          CONJUNCTIONS
          {loading && <span className={styles.spinner} />}
        </span>
        <button className={styles.toggleBtn} onClick={onToggle}>
          {open ? '◀' : '▶'}
        </button>
      </div>
      {open && (
        <div className={styles.list}>
          {conjunctions.map((c) => (
            <div key={c.id}>
              <ConjunctionCard
                conjunction={c}
                selected={selectedId === c.id}
                onClick={() => setSelected(selectedId === c.id ? null : c.id)}
              />
              {selectedId === c.id && <ConjunctionDetail conjunctionId={c.id} />}
            </div>
          ))}
          {conjunctions.length === 0 && !loading && (
            <p className={styles.empty}>No active conjunctions</p>
          )}
        </div>
      )}
    </aside>
  )
}
```

- [ ] **Step 3: Create ConjunctionPanel CSS**

Create `frontend/src/components/ConjunctionPanel/ConjunctionPanel.module.css`:
```css
.panel {
  position: relative;
  height: 100%;
  background: var(--bg-surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
  flex-shrink: 0;
  z-index: 10;
}
.panelOpen { width: 320px; }
.panelClosed { width: 32px; }
.header {
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 10px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.headerLabel {
  font-size: 10px;
  color: var(--text-secondary);
  letter-spacing: 1px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.spinner {
  display: inline-block;
  width: 8px;
  height: 8px;
  border: 1px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.toggleBtn {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 10px;
  padding: 2px 4px;
}
.toggleBtn:hover { color: var(--text-primary); }
.list {
  flex: 1;
  overflow-y: auto;
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.card {
  background: var(--bg-base);
  border-left: 2px solid var(--nominal);
  border-radius: 3px;
  padding: 6px 8px;
  cursor: pointer;
  transition: background 0.1s;
}
.card:hover { background: var(--bg-raised); }
.cardSelected { background: var(--bg-raised); outline: 1px solid var(--border); }
.cardTitle { font-size: 11px; color: var(--text-primary); margin-bottom: 3px; }
.cardMeta { display: flex; justify-content: space-between; font-size: 10px; }
.tca { color: var(--text-secondary); }
.mlRow { display: flex; gap: 8px; margin-top: 3px; }
.mlLabel { font-size: 9px; background: var(--bg-raised); padding: 1px 4px; border-radius: 2px; color: var(--text-secondary); }
.empty { color: var(--text-secondary); font-size: 12px; padding: 16px; text-align: center; }
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ConjunctionPanel/
git commit -m "feat(frontend): ConjunctionPanel and ConjunctionCard components"
```

---

## Task 6: ConjunctionDetail with Recharts

**Files:**
- Create: `frontend/src/components/ConjunctionPanel/ConjunctionDetail.tsx`

- [ ] **Step 1: Create ConjunctionDetail**

Create `frontend/src/components/ConjunctionPanel/ConjunctionDetail.tsx`:
```tsx
import { useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { useConjunctionStore } from '../../stores/useConjunctionStore'
import styles from './ConjunctionPanel.module.css'

interface Props {
  conjunctionId: number
}

export function ConjunctionDetail({ conjunctionId }: Props) {
  const { detail, fetchDetail } = useConjunctionStore()

  useEffect(() => {
    fetchDetail(conjunctionId)
  }, [conjunctionId, fetchDetail])

  if (!detail || detail.id !== conjunctionId) {
    return <div className={styles.detailLoading}>Loading...</div>
  }

  const chartData = [
    { name: 'Classical', pc: detail.pc_classical ?? 0, fill: 'var(--accent)' },
    { name: 'ML', pc: detail.pc_ml ?? 0, fill: '#3fb950' },
  ]

  return (
    <div className={styles.detail}>
      <div className={styles.detailRow}>
        <span className={styles.detailLabel}>Miss distance</span>
        <span>{detail.miss_distance_km.toFixed(3)} km</span>
      </div>
      {detail.relative_velocity_kms != null && (
        <div className={styles.detailRow}>
          <span className={styles.detailLabel}>Rel. velocity</span>
          <span>{detail.relative_velocity_kms.toFixed(2)} km/s</span>
        </div>
      )}
      <div className={styles.chartLabel}>Pc Comparison</div>
      <ResponsiveContainer width="100%" height={80}>
        <BarChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
          <XAxis dataKey="name" tick={{ fill: 'var(--text-secondary)', fontSize: 9 }} />
          <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 9 }} tickFormatter={(v) => v.toExponential(0)} />
          <Tooltip
            formatter={(v: number) => v.toExponential(2)}
            contentStyle={{ background: 'var(--bg-raised)', border: '1px solid var(--border)', fontSize: 10 }}
          />
          <Bar dataKey="pc" radius={[2, 2, 0, 0]}>
            {chartData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
```

Add to `ConjunctionPanel.module.css`:
```css
.detail {
  background: var(--bg-base);
  border-left: 2px solid var(--border);
  border-radius: 0 0 3px 3px;
  padding: 8px;
  margin-top: -4px;
}
.detailRow {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  margin-bottom: 4px;
  color: var(--text-primary);
}
.detailLabel { color: var(--text-secondary); }
.detailLoading { padding: 8px; font-size: 10px; color: var(--text-secondary); }
.chartLabel { font-size: 9px; color: var(--text-secondary); margin: 6px 0 2px; letter-spacing: 1px; }
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ConjunctionPanel/ConjunctionDetail.tsx frontend/src/components/ConjunctionPanel/ConjunctionPanel.module.css
git commit -m "feat(frontend): ConjunctionDetail with Recharts Pc comparison"
```

---

## Task 7: GlobePage (CesiumJS)

**Files:**
- Create: `frontend/src/components/Globe/GlobePage.tsx`
- Create: `frontend/src/components/Globe/GlobePage.module.css`

- [ ] **Step 1: Create GlobePage**

Create `frontend/src/components/Globe/GlobePage.tsx`:
```tsx
import { useState, useRef } from 'react'
import { Viewer, PointPrimitiveCollection, PointPrimitive, Entity, PolylineGraphics } from 'resium'
import { Cartesian3, Color } from 'cesium'
import { useConjunctionStore } from '../../stores/useConjunctionStore'
import { useSatelliteStore } from '../../stores/useSatelliteStore'
import { usePolling } from '../../hooks/usePolling'
import { ConjunctionPanel } from '../ConjunctionPanel/ConjunctionPanel'
import styles from './GlobePage.module.css'

function regimeColor(regime: string | null): Color {
  switch (regime) {
    case 'LEO': return Color.fromCssColorString('#388bfd')
    case 'MEO': return Color.fromCssColorString('#e3b341')
    case 'GEO': return Color.fromCssColorString('#3fb950')
    default: return Color.fromCssColorString('#8b949e')
  }
}

export function GlobePage() {
  const [panelOpen, setPanelOpen] = useState(true)
  const viewerRef = useRef<{ cesiumElement: Cesium.Viewer } | null>(null)

  const { conjunctions, selectedId } = useConjunctionStore()
  const { satellites } = useSatelliteStore()
  const fetchConjunctions = useConjunctionStore((s) => s.fetch)
  const fetchSatellites = useSatelliteStore((s) => s.fetch)

  usePolling(fetchConjunctions, 30_000)
  usePolling(fetchSatellites, 30_000)

  const selected = conjunctions.find((c) => c.id === selectedId) ?? null

  return (
    <div className={styles.page}>
      <ConjunctionPanel open={panelOpen} onToggle={() => setPanelOpen((o) => !o)} />
      <div className={styles.globeWrap}>
        <Viewer
          ref={viewerRef}
          full
          timeline={false}
          animation={false}
          baseLayerPicker={false}
          navigationHelpButton={false}
          homeButton={false}
          sceneModePicker={false}
          geocoder={false}
          className={styles.viewer}
        >
          <PointPrimitiveCollection>
            {satellites.map((sat) => {
              if (sat.inclination_deg == null || sat.altitude_km == null) return null
              // Place point at approximate position using inclination + arbitrary longitude
              const lon = ((sat.norad_id * 137.5) % 360) - 180
              const lat = Math.sin((sat.inclination_deg * Math.PI) / 180) * sat.inclination_deg * 0.5
              return (
                <PointPrimitive
                  key={sat.norad_id}
                  position={Cartesian3.fromDegrees(lon, lat, (sat.altitude_km + 6371) * 1000)}
                  color={regimeColor(sat.orbital_regime)}
                  pixelSize={3}
                />
              )
            })}
          </PointPrimitiveCollection>

          {selected && (
            <Entity name={`${selected.primary_name} × ${selected.secondary_name}`}>
              <PolylineGraphics
                positions={[
                  Cartesian3.fromDegrees(-80, 30, 420_000),
                  Cartesian3.fromDegrees(-75, 35, 430_000),
                ]}
                width={2}
                material={Color.RED.withAlpha(0.8)}
              />
            </Entity>
          )}
        </Viewer>
      </div>
    </div>
  )
}
```

**Note:** Satellite positions above use a placeholder formula (longitude from NORAD ID hash, latitude from inclination). Real positions require running SGP4 via `satellite.js` on the TLE — that is a Phase 6 enhancement. The placeholder still renders orbit regime distribution meaningfully.

- [ ] **Step 2: Create GlobePage CSS**

Create `frontend/src/components/Globe/GlobePage.module.css`:
```css
.page {
  flex: 1;
  display: flex;
  overflow: hidden;
}
.globeWrap {
  flex: 1;
  position: relative;
}
.viewer {
  width: 100% !important;
  height: 100% !important;
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Globe/
git commit -m "feat(frontend): GlobePage with CesiumJS, satellite points, conjunction highlight"
```

---

## Task 8: SatellitesPage

**Files:**
- Create: `frontend/src/pages/SatellitesPage/SatellitesPage.tsx`
- Create: `frontend/src/pages/SatellitesPage/SatellitesPage.module.css`

- [ ] **Step 1: Create SatellitesPage**

Create `frontend/src/pages/SatellitesPage/SatellitesPage.tsx`:
```tsx
import { useEffect } from 'react'
import { useSatelliteStore } from '../../stores/useSatelliteStore'
import { usePolling } from '../../hooks/usePolling'
import styles from './SatellitesPage.module.css'

export function SatellitesPage() {
  const { satellites, total, page, limit, search, loading, fetch, setSearch, setPage } = useSatelliteStore()

  usePolling(fetch, 30_000)

  const totalPages = Math.ceil(total / limit)

  function handleSearch(e: React.ChangeEvent<HTMLInputElement>) {
    setSearch(e.target.value)
  }

  useEffect(() => { fetch() }, [page, search])

  return (
    <div className={styles.page}>
      <div className={styles.toolbar}>
        <h1 className={styles.title}>Satellite Catalog</h1>
        <input
          className={styles.search}
          placeholder="Search name or NORAD ID…"
          value={search}
          onChange={handleSearch}
        />
        <span className={styles.count}>{total.toLocaleString()} objects</span>
      </div>

      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>NORAD ID</th>
              <th>Name</th>
              <th>Type</th>
              <th>Regime</th>
              <th>Inclination</th>
              <th>Altitude (km)</th>
              <th>Epoch</th>
            </tr>
          </thead>
          <tbody>
            {satellites.map((s) => (
              <tr key={s.norad_id}>
                <td className={styles.mono}>{s.norad_id}</td>
                <td>{s.name}</td>
                <td className={styles.secondary}>{s.object_type ?? '—'}</td>
                <td>
                  {s.orbital_regime && (
                    <span className={`${styles.regime} ${styles[`regime_${s.orbital_regime}`]}`}>
                      {s.orbital_regime}
                    </span>
                  )}
                </td>
                <td className={styles.mono}>{s.inclination_deg?.toFixed(2) ?? '—'}°</td>
                <td className={styles.mono}>{s.altitude_km?.toFixed(0) ?? '—'}</td>
                <td className={styles.secondary}>{s.epoch ? new Date(s.epoch).toLocaleDateString() : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {loading && <div className={styles.loading}>Loading…</div>}
      </div>

      <div className={styles.pagination}>
        <button disabled={page <= 1} onClick={() => setPage(page - 1)}>← Prev</button>
        <span>Page {page} / {totalPages || 1}</span>
        <button disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next →</button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Create SatellitesPage CSS**

Create `frontend/src/pages/SatellitesPage/SatellitesPage.module.css`:
```css
.page { display: flex; flex-direction: column; height: 100%; overflow: hidden; padding: 16px; gap: 12px; }
.toolbar { display: flex; align-items: center; gap: 16px; flex-shrink: 0; }
.title { font-size: 16px; font-weight: 600; color: var(--text-primary); }
.search {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 12px;
  color: var(--text-primary);
  font-size: 13px;
  width: 260px;
}
.search:focus { outline: none; border-color: var(--accent); }
.count { margin-left: auto; color: var(--text-secondary); font-size: 12px; }
.tableWrap { flex: 1; overflow-y: auto; }
.table { width: 100%; border-collapse: collapse; font-size: 12px; }
.table th {
  text-align: left;
  padding: 8px 12px;
  color: var(--text-secondary);
  font-size: 10px;
  letter-spacing: 1px;
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  background: var(--bg-base);
}
.table td { padding: 7px 12px; border-bottom: 1px solid color-mix(in srgb, var(--border) 50%, transparent); }
.table tr:hover td { background: var(--bg-surface); }
.mono { font-family: monospace; }
.secondary { color: var(--text-secondary); }
.regime { padding: 2px 6px; border-radius: 3px; font-size: 10px; font-weight: 600; }
.regime_LEO { background: color-mix(in srgb, var(--nominal) 15%, transparent); color: var(--nominal); }
.regime_MEO { background: color-mix(in srgb, var(--warning) 15%, transparent); color: var(--warning); }
.regime_GEO { background: color-mix(in srgb, #3fb950 15%, transparent); color: #3fb950; }
.loading { text-align: center; padding: 24px; color: var(--text-secondary); }
.pagination { display: flex; align-items: center; gap: 16px; justify-content: center; flex-shrink: 0; padding: 8px; }
.pagination button {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  color: var(--text-primary);
  padding: 4px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}
.pagination button:disabled { opacity: 0.4; cursor: not-allowed; }
.pagination span { color: var(--text-secondary); font-size: 12px; }
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/SatellitesPage/
git commit -m "feat(frontend): SatellitesPage with search and pagination"
```

---

## Task 9: AlertsPage

**Files:**
- Create: `frontend/src/pages/AlertsPage/AlertsPage.tsx`
- Create: `frontend/src/pages/AlertsPage/AlertsPage.module.css`

- [ ] **Step 1: Create AlertsPage**

Create `frontend/src/pages/AlertsPage/AlertsPage.tsx`:
```tsx
import { useState, useEffect } from 'react'
import { useAlertStore } from '../../stores/useAlertStore'
import type { AlertConfigCreate } from '../../api/types'
import styles from './AlertsPage.module.css'

const EMPTY_FORM: AlertConfigCreate = { pc_threshold: 1e-4, enabled: true }

export function AlertsPage() {
  const { alerts, loading, error, fetch, create, update, remove } = useAlertStore()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<AlertConfigCreate>(EMPTY_FORM)
  const [editId, setEditId] = useState<number | null>(null)

  useEffect(() => { fetch() }, [])

  function startEdit(id: number) {
    const a = alerts.find((x) => x.id === id)!
    setForm({ pc_threshold: a.pc_threshold, enabled: a.enabled, notification_channels: a.notification_channels ?? undefined })
    setEditId(id)
    setShowForm(true)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (editId != null) {
      await update(editId, form)
      setEditId(null)
    } else {
      await create(form)
    }
    setForm(EMPTY_FORM)
    setShowForm(false)
  }

  return (
    <div className={styles.page}>
      <div className={styles.toolbar}>
        <h1 className={styles.title}>Alert Configuration</h1>
        <button className={styles.addBtn} onClick={() => { setShowForm(true); setEditId(null); setForm(EMPTY_FORM) }}>
          + New Alert
        </button>
      </div>

      {error && <div className={styles.error}>{error}</div>}

      {showForm && (
        <form className={styles.form} onSubmit={handleSubmit}>
          <label className={styles.field}>
            <span>Pc Threshold</span>
            <input
              type="number"
              step="any"
              value={form.pc_threshold}
              onChange={(e) => setForm({ ...form, pc_threshold: parseFloat(e.target.value) })}
              className={styles.input}
            />
          </label>
          <label className={styles.field}>
            <span>Enabled</span>
            <input
              type="checkbox"
              checked={form.enabled ?? true}
              onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
            />
          </label>
          <div className={styles.formActions}>
            <button type="submit" className={styles.saveBtn}>{editId ? 'Update' : 'Create'}</button>
            <button type="button" className={styles.cancelBtn} onClick={() => { setShowForm(false); setEditId(null) }}>Cancel</button>
          </div>
        </form>
      )}

      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>ID</th>
              <th>Pc Threshold</th>
              <th>Watched NORADs</th>
              <th>Channels</th>
              <th>Enabled</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {alerts.map((a) => (
              <tr key={a.id}>
                <td className={styles.mono}>{a.id}</td>
                <td className={styles.mono}>{a.pc_threshold.toExponential(1)}</td>
                <td className={styles.secondary}>{a.watched_norad_ids?.join(', ') || 'all'}</td>
                <td className={styles.secondary}>
                  {a.notification_channels ? Object.entries(a.notification_channels).map(([k, v]) => `${k}: ${v}`).join(', ') : '—'}
                </td>
                <td>
                  <span className={a.enabled ? styles.enabled : styles.disabled}>
                    {a.enabled ? 'ON' : 'OFF'}
                  </span>
                </td>
                <td className={styles.actions}>
                  <button className={styles.editBtn} onClick={() => startEdit(a.id)}>Edit</button>
                  <button className={styles.deleteBtn} onClick={() => remove(a.id)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {loading && <div className={styles.loading}>Loading…</div>}
        {!loading && alerts.length === 0 && <div className={styles.loading}>No alerts configured.</div>}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Create AlertsPage CSS**

Create `frontend/src/pages/AlertsPage/AlertsPage.module.css`:
```css
.page { display: flex; flex-direction: column; height: 100%; overflow: hidden; padding: 16px; gap: 12px; }
.toolbar { display: flex; align-items: center; gap: 16px; flex-shrink: 0; }
.title { font-size: 16px; font-weight: 600; }
.addBtn {
  margin-left: auto;
  background: var(--accent);
  color: #000;
  border: none;
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
}
.form {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 14px;
  display: flex;
  gap: 16px;
  align-items: flex-end;
  flex-shrink: 0;
}
.field { display: flex; flex-direction: column; gap: 4px; font-size: 11px; color: var(--text-secondary); }
.input {
  background: var(--bg-base);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 5px 8px;
  color: var(--text-primary);
  font-size: 12px;
  width: 120px;
}
.formActions { display: flex; gap: 8px; }
.saveBtn { background: var(--accent); color: #000; border: none; padding: 5px 14px; border-radius: 4px; cursor: pointer; font-size: 12px; }
.cancelBtn { background: var(--bg-raised); color: var(--text-primary); border: 1px solid var(--border); padding: 5px 14px; border-radius: 4px; cursor: pointer; font-size: 12px; }
.tableWrap { flex: 1; overflow-y: auto; }
.table { width: 100%; border-collapse: collapse; font-size: 12px; }
.table th { text-align: left; padding: 8px 12px; color: var(--text-secondary); font-size: 10px; letter-spacing: 1px; border-bottom: 1px solid var(--border); position: sticky; top: 0; background: var(--bg-base); }
.table td { padding: 8px 12px; border-bottom: 1px solid color-mix(in srgb, var(--border) 50%, transparent); }
.table tr:hover td { background: var(--bg-surface); }
.mono { font-family: monospace; }
.secondary { color: var(--text-secondary); }
.enabled { color: #3fb950; font-size: 10px; font-weight: 600; }
.disabled { color: var(--text-secondary); font-size: 10px; }
.actions { display: flex; gap: 6px; }
.editBtn { background: none; border: 1px solid var(--border); color: var(--text-secondary); padding: 3px 8px; border-radius: 3px; cursor: pointer; font-size: 11px; }
.editBtn:hover { color: var(--text-primary); }
.deleteBtn { background: none; border: 1px solid color-mix(in srgb, var(--critical) 40%, transparent); color: var(--critical); padding: 3px 8px; border-radius: 3px; cursor: pointer; font-size: 11px; }
.loading { text-align: center; padding: 24px; color: var(--text-secondary); }
.error { background: color-mix(in srgb, var(--critical) 10%, transparent); border: 1px solid color-mix(in srgb, var(--critical) 30%, transparent); color: var(--critical); padding: 8px 12px; border-radius: 4px; font-size: 12px; }
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/AlertsPage/
git commit -m "feat(frontend): AlertsPage with create/edit/delete"
```

---

## Task 10: Wire Up App.tsx and main.tsx

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/main.tsx`

- [ ] **Step 1: Replace App.tsx**

Replace entire `frontend/src/App.tsx`:
```tsx
import { Routes, Route, Navigate } from 'react-router-dom'
import { Nav } from './components/Nav/Nav'
import { GlobePage } from './components/Globe/GlobePage'
import { SatellitesPage } from './pages/SatellitesPage/SatellitesPage'
import { AlertsPage } from './pages/AlertsPage/AlertsPage'
import styles from './App.module.css'

export default function App() {
  return (
    <div className={styles.app}>
      <Nav />
      <main className={styles.main}>
        <Routes>
          <Route path="/" element={<GlobePage />} />
          <Route path="/satellites" element={<SatellitesPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}
```

- [ ] **Step 2: Create App.module.css**

Create `frontend/src/App.module.css`:
```css
.app { height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
.main { flex: 1; overflow: hidden; display: flex; flex-direction: column; }
```

- [ ] **Step 3: Replace main.tsx**

Replace entire `frontend/src/main.tsx`:
```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>
)
```

- [ ] **Step 4: Run dev server — verify app loads**

```bash
npm run dev
```
Expected: http://localhost:5173 loads, shows "COLLIDER" nav, globe renders, `/satellites` and `/alerts` routes work.

- [ ] **Step 5: Run all tests**

```bash
npx vitest run
```
Expected: 5+ tests passing, 0 failures.

- [ ] **Step 6: Run TypeScript check**

```bash
npx tsc --noEmit
```
Expected: 0 errors.

- [ ] **Step 7: Final commit**

```bash
git add frontend/src/App.tsx frontend/src/App.module.css frontend/src/main.tsx
git commit -m "feat(frontend): wire up React Router, Nav, all routes — Phase 5 frontend complete"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Globe-first layout with left panel → GlobePage + ConjunctionPanel
- [x] Conjunction list sorted by Pc → `sort()` in useConjunctionStore.fetch
- [x] Color-coded risk (red/yellow/blue) → `pcColor()` in ConjunctionCard
- [x] Classical vs ML Pc side-by-side → ConjunctionDetail Recharts BarChart
- [x] `/satellites` → SatellitesPage with search + pagination
- [x] `/alerts` CRUD → AlertsPage
- [x] Zustand stores (conjunctions, satellites, alerts) → Task 3
- [x] Typed API client → Task 2
- [x] 30s polling → usePolling hook, used in GlobePage and SatellitesPage
- [x] CSS tokens (dark theme) → Task 1 index.css
- [x] CesiumJS + Resium → GlobePage
- [x] Recharts → ConjunctionDetail
- [x] React Router v6 → App.tsx + main.tsx

**Gaps / deferred (by design):**
- WebSocket — deferred, WS backend is a stub
- Satellite positions use placeholder formula — real SGP4 via satellite.js is Phase 6
- Email/Slack delivery — Phase 6
