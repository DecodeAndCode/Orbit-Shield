import { create } from "zustand";

export type Regime = "LEO" | "MEO" | "GEO" | "HEO";
export type ObjectType = "PAYLOAD" | "DEBRIS" | "ROCKET BODY" | "UNKNOWN";
export type RiskLevel = "high" | "medium" | "low";

interface FilterState {
  regimes: Set<Regime>;
  objectTypes: Set<ObjectType>;
  riskLevels: Set<RiskLevel>;
  minPc: number | null; // null = no min
  hoursAhead: number;
  showPointCloud: boolean;
  showOrbits: boolean;
}

export interface HoverInfo {
  norad_id: number;
  name: string | null;
  object_type: string | null;
  country: string | null;
  alt_km: number;
  lat_deg: number;
  lon_deg: number;
  regime: Regime;
  screenX: number;
  screenY: number;
}

interface ColliderStore extends FilterState {
  selectedConjunctionId: number | null;
  selectConjunction: (id: number | null) => void;

  hoveredSat: HoverInfo | null;
  setHoveredSat: (h: HoverInfo | null) => void;

  focusNoradId: number | null;
  focusOnSat: (id: number | null) => void;

  // Layout
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  detailCollapsed: boolean;
  toggleDetail: () => void;
  alertModalOpen: boolean;
  setAlertModalOpen: (open: boolean) => void;
  filterDrawerOpen: boolean; // mobile
  setFilterDrawerOpen: (open: boolean) => void;

  // Filter mutators
  toggleRegime: (r: Regime) => void;
  toggleObjectType: (t: ObjectType) => void;
  toggleRiskLevel: (l: RiskLevel) => void;
  setMinPc: (v: number | null) => void;
  setHoursAhead: (h: number) => void;
  setShowPointCloud: (v: boolean) => void;
  setShowOrbits: (v: boolean) => void;
  resetFilters: () => void;
}

const DEFAULT_REGIMES: Regime[] = ["LEO", "MEO", "GEO", "HEO"];
const DEFAULT_TYPES: ObjectType[] = ["PAYLOAD", "DEBRIS", "ROCKET BODY", "UNKNOWN"];
const DEFAULT_RISKS: RiskLevel[] = ["high", "medium", "low"];

export const useColliderStore = create<ColliderStore>((set) => ({
  selectedConjunctionId: null,
  selectConjunction: (id) => set({ selectedConjunctionId: id }),

  hoveredSat: null,
  setHoveredSat: (h) => set({ hoveredSat: h }),

  focusNoradId: null,
  focusOnSat: (id) => set({ focusNoradId: id }),

  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  detailCollapsed: false,
  toggleDetail: () => set((s) => ({ detailCollapsed: !s.detailCollapsed })),
  alertModalOpen: false,
  setAlertModalOpen: (open) => set({ alertModalOpen: open }),
  filterDrawerOpen: false,
  setFilterDrawerOpen: (open) => set({ filterDrawerOpen: open }),

  regimes: new Set(DEFAULT_REGIMES),
  objectTypes: new Set(DEFAULT_TYPES),
  riskLevels: new Set(DEFAULT_RISKS),
  minPc: null,
  hoursAhead: 72,
  showPointCloud: true,
  showOrbits: true,

  toggleRegime: (r) =>
    set((s) => {
      const next = new Set(s.regimes);
      next.has(r) ? next.delete(r) : next.add(r);
      return { regimes: next };
    }),
  toggleObjectType: (t) =>
    set((s) => {
      const next = new Set(s.objectTypes);
      next.has(t) ? next.delete(t) : next.add(t);
      return { objectTypes: next };
    }),
  toggleRiskLevel: (l) =>
    set((s) => {
      const next = new Set(s.riskLevels);
      next.has(l) ? next.delete(l) : next.add(l);
      return { riskLevels: next };
    }),
  setMinPc: (v) => set({ minPc: v }),
  setHoursAhead: (h) => set({ hoursAhead: h }),
  setShowPointCloud: (v) => set({ showPointCloud: v }),
  setShowOrbits: (v) => set({ showOrbits: v }),
  resetFilters: () =>
    set({
      regimes: new Set(DEFAULT_REGIMES),
      objectTypes: new Set(DEFAULT_TYPES),
      riskLevels: new Set(DEFAULT_RISKS),
      minPc: null,
      hoursAhead: 72,
      showPointCloud: true,
      showOrbits: true,
    }),
}));

export function altKmToRegime(altKm: number): Regime {
  if (altKm < 2000) return "LEO";
  if (altKm < 35000) return "MEO";
  if (altKm < 36500) return "GEO";
  return "HEO";
}

export function pcToRiskLevel(pc: number | null): RiskLevel {
  if (pc === null) return "low";
  if (pc >= 1e-4) return "high";
  if (pc >= 1e-6) return "medium";
  return "low";
}
