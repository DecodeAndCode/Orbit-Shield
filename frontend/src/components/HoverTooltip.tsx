import { useEffect, useState } from "react";
import { useOrbitShieldStore } from "../stores/orbitShieldStore";
import type { SatelliteResponse } from "../api/types";

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

const regimeColors: Record<string, string> = {
  LEO: "var(--os-regime-leo)",
  MEO: "var(--os-regime-meo)",
  GEO: "var(--os-regime-geo)",
  HEO: "var(--os-regime-heo)",
};

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

  const R_E = 6378.137;
  const MU = 398600.4418;
  const r = R_E + hover.alt_km;
  const speed_kms = Math.sqrt(MU / r);
  const period_min = (2 * Math.PI * Math.sqrt((r * r * r) / MU)) / 60;

  const regimeColor = regimeColors[hover.regime] ?? "var(--os-regime-leo)";

  return (
    <div
      className="os-hover-tip"
      style={{
        left: Math.min(hover.screenX + 16, window.innerWidth - 300),
        top: Math.min(hover.screenY + 16, window.innerHeight - 200),
        minWidth: 220,
        maxWidth: 280,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <div
          style={{
            fontSize: 13, fontWeight: 600, color: "var(--os-fg1)",
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", minWidth: 0, flex: 1,
          }}
        >
          {meta?.name || `Object #${hover.norad_id}`}
        </div>
        <span
          className="os-pill"
          style={{
            color: regimeColor,
            background: `color-mix(in srgb, ${regimeColor} 15%, transparent)`,
            flexShrink: 0,
          }}
        >
          {hover.regime}
        </span>
      </div>
      <div className="mono" style={{ fontSize: 10, color: "var(--os-fg3)", marginBottom: 8 }}>
        NORAD #{hover.norad_id}
        {meta?.country && <span> · {meta.country}</span>}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "4px 12px", fontSize: 11 }}>
        <span style={{ color: "var(--os-fg3)" }}>Type</span>
        <span className="mono" style={{ textAlign: "right", color: "var(--os-fg1)" }}>
          {meta?.object_type ?? "—"}
        </span>
        <span style={{ color: "var(--os-fg3)" }}>Altitude</span>
        <span className="mono tabular" style={{ textAlign: "right", color: "var(--os-fg1)" }}>
          {hover.alt_km.toFixed(1)} km
        </span>
        <span style={{ color: "var(--os-fg3)" }}>Speed</span>
        <span className="mono tabular" style={{ textAlign: "right", color: "var(--os-fg1)" }}>
          {speed_kms.toFixed(2)} km/s
        </span>
        <span style={{ color: "var(--os-fg3)" }}>Period</span>
        <span className="mono tabular" style={{ textAlign: "right", color: "var(--os-fg1)" }}>
          {period_min.toFixed(1)} min
        </span>
        <span style={{ color: "var(--os-fg3)" }}>Inclination</span>
        <span className="mono tabular" style={{ textAlign: "right", color: "var(--os-fg1)" }}>
          {meta?.inclination !== null && meta?.inclination !== undefined
            ? `${meta.inclination.toFixed(2)}°`
            : "—"}
        </span>
      </div>
      <div
        style={{
          marginTop: 8, paddingTop: 8,
          borderTop: "1px solid var(--os-border-subtle)",
          fontSize: 9, textTransform: "uppercase", letterSpacing: "0.14em",
          color: "var(--os-signal)",
        }}
      >
        Click to focus
      </div>
    </div>
  );
}
