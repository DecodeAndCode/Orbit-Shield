import { useEffect, useState } from "react";
import { useOrbitShieldStore } from "../stores/orbitShieldStore";
import type { SatelliteResponse } from "../api/types";

// Simple in-memory cache for per-norad_id satellite metadata fetches.
const metaCache = new Map<number, SatelliteResponse | null>();

async function fetchSatMeta(
  norad_id: number
): Promise<SatelliteResponse | null> {
  if (metaCache.has(norad_id)) return metaCache.get(norad_id)!;
  try {
    const res = await fetch(`/api/satellites?search=${norad_id}&limit=1`);
    if (!res.ok) throw new Error();
    const data = (await res.json()) as { items: SatelliteResponse[] };
    const item = data.items.find((s) => s.norad_id === norad_id) ?? null;
    metaCache.set(norad_id, item);
    return item;
  } catch {
    metaCache.set(norad_id, null);
    return null;
  }
}

export default function HoverTooltip() {
  const hover = useOrbitShieldStore((s) => s.hoveredSat);
  const [meta, setMeta] = useState<SatelliteResponse | null>(null);

  useEffect(() => {
    if (!hover) {
      setMeta(null);
      return;
    }
    let cancelled = false;
    fetchSatMeta(hover.norad_id).then((m) => {
      if (!cancelled) setMeta(m);
    });
    return () => {
      cancelled = true;
    };
  }, [hover?.norad_id]);

  if (!hover) return null;

  // Orbital velocity approximation for LEO/MEO/GEO — circular orbit v = sqrt(mu/r)
  const R_E = 6378.137;
  const MU = 398600.4418;
  const r = R_E + hover.alt_km;
  const speed_kms = Math.sqrt(MU / r);
  const period_min = (2 * Math.PI * Math.sqrt((r * r * r) / MU)) / 60;

  const regimeColors: Record<string, string> = {
    LEO: "#22d3ee",
    MEO: "#fb923c",
    GEO: "#c084fc",
    HEO: "#f472b6",
  };

  return (
    <div
      className="absolute pointer-events-none z-40 bg-[var(--color-bg-card)]/95 backdrop-blur-sm border border-[var(--color-border-strong)] rounded-md shadow-2xl p-3 min-w-[220px] max-w-[280px]"
      style={{
        left: Math.min(hover.screenX + 16, window.innerWidth - 300),
        top: Math.min(hover.screenY + 16, window.innerHeight - 200),
      }}
    >
      <div className="flex items-center justify-between mb-1.5">
        <div className="text-sm font-semibold text-[var(--color-text-primary)] truncate">
          {meta?.name || `Object #${hover.norad_id}`}
        </div>
        <span
          className="text-[9px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded"
          style={{
            color: regimeColors[hover.regime],
            backgroundColor: regimeColors[hover.regime] + "22",
          }}
        >
          {hover.regime}
        </span>
      </div>
      <div className="text-[10px] mono text-[var(--color-text-muted)] mb-2">
        NORAD #{hover.norad_id}
        {meta?.country && <span> · {meta.country}</span>}
      </div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
        <span className="text-[var(--color-text-muted)]">Type</span>
        <span className="text-[var(--color-text-primary)] text-right mono">
          {meta?.object_type ?? "—"}
        </span>
        <span className="text-[var(--color-text-muted)]">Altitude</span>
        <span className="text-[var(--color-text-primary)] text-right mono tabular">
          {hover.alt_km.toFixed(1)} km
        </span>
        <span className="text-[var(--color-text-muted)]">Speed</span>
        <span className="text-[var(--color-text-primary)] text-right mono tabular">
          {speed_kms.toFixed(2)} km/s
        </span>
        <span className="text-[var(--color-text-muted)]">Period</span>
        <span className="text-[var(--color-text-primary)] text-right mono tabular">
          {period_min.toFixed(1)} min
        </span>
        <span className="text-[var(--color-text-muted)]">Inclination</span>
        <span className="text-[var(--color-text-primary)] text-right mono tabular">
          {meta?.inclination !== null && meta?.inclination !== undefined
            ? `${meta.inclination.toFixed(2)}°`
            : "—"}
        </span>
        <span className="text-[var(--color-text-muted)]">RCS</span>
        <span className="text-[var(--color-text-primary)] text-right mono">
          {meta?.rcs_size ?? "—"}
        </span>
        <span className="text-[var(--color-text-muted)]">Position</span>
        <span className="text-[var(--color-text-primary)] text-right mono tabular text-[10px]">
          {hover.lat_deg.toFixed(2)}°, {hover.lon_deg.toFixed(2)}°
        </span>
      </div>
      <div className="mt-2 pt-2 border-t border-[var(--color-border)] text-[9px] uppercase tracking-wider text-[var(--color-accent)]">
        Click to focus
      </div>
    </div>
  );
}
