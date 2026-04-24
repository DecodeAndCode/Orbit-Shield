import { useEffect, useState } from "react";
import { useOrbitShieldStore, altKmToRegime } from "../stores/orbitShieldStore";
import type { SatelliteResponse } from "../api/types";

const metaCache = new Map<number, SatelliteResponse | null>();

async function fetchMeta(
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

export default function SatDetailCard() {
  const clickedSatId = useOrbitShieldStore((s) => s.clickedSatId);
  const setClickedSat = useOrbitShieldStore((s) => s.setClickedSat);
  const [meta, setMeta] = useState<SatelliteResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (clickedSatId === null) {
      setMeta(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    fetchMeta(clickedSatId).then((m) => {
      if (!cancelled) {
        setMeta(m);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [clickedSatId]);

  if (clickedSatId === null) return null;

  const perigee = meta?.perigee_alt_km ?? null;
  const apogee = meta?.apogee_alt_km ?? null;
  const meanAlt =
    perigee !== null && apogee !== null ? (perigee + apogee) / 2 : null;
  const regime =
    (meta?.regime as string | null) ??
    (meanAlt !== null ? altKmToRegime(meanAlt) : "LEO");
  const regimeColor = regimeColors[regime] ?? "var(--os-regime-leo)";

  const status = meta?.object_type === "DEBRIS" ? "DEBRIS" : "ACTIVE";
  const statusColor =
    status === "DEBRIS" ? "var(--os-risk-high)" : "var(--os-risk-low)";

  return (
    <div className="os-satcard">
      <div className="os-satcard-bar" style={{ background: regimeColor }} />
      <div className="os-satcard-body">
        <div className="os-satcard-top">
          <div style={{ minWidth: 0, flex: 1 }}>
            <div className="os-satcard-title" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {loading ? "Loading…" : meta?.name || `Object #${clickedSatId}`}
            </div>
            <div className="os-satcard-pills">
              <span
                className="os-pill"
                style={{ color: statusColor, background: `color-mix(in srgb, ${statusColor} 15%, transparent)` }}
              >
                {status}
              </span>
              <span
                className="os-pill"
                style={{ color: regimeColor, background: `color-mix(in srgb, ${regimeColor} 15%, transparent)` }}
              >
                {regime}
              </span>
            </div>
          </div>
          <button
            onClick={() => setClickedSat(null)}
            className="os-icon-btn"
            aria-label="Close"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className="os-satcard-meta">
          <div className="os-field-label">NORAD ID</div>
          <div className="mono os-fg1">{clickedSatId}</div>
          <div className="os-field-label mt">Source</div>
          <div className="mono os-text-signal">SPACE-TRACK</div>
        </div>

        <div className="os-satcard-grid">
          <span>Type</span>
          <span className="mono">{meta?.object_type ?? "—"}</span>
          <span>Country</span>
          <span>{meta?.country ?? "—"}</span>
          <span>Perigee</span>
          <span className="mono">
            {perigee !== null ? `${perigee.toFixed(1)} km` : "—"}
          </span>
          <span>Apogee</span>
          <span className="mono">
            {apogee !== null ? `${apogee.toFixed(1)} km` : "—"}
          </span>
          <span>Inclination</span>
          <span className="mono">
            {meta?.inclination !== null && meta?.inclination !== undefined
              ? `${meta.inclination.toFixed(2)}°`
              : "—"}
          </span>
          <span>RCS</span>
          <span className="mono">{meta?.rcs_size ?? "—"}</span>
          <span>Launch</span>
          <span className="mono">
            {meta?.launch_date
              ? new Date(meta.launch_date).toISOString().slice(0, 10)
              : "—"}
          </span>
        </div>

        <div className="os-satcard-actions">
          <button
            className="os-chrome-btn"
            onClick={() =>
              window.open(
                `https://www.space-track.org/#catalog?predicates=NORAD_CAT_ID=${clickedSatId}`,
                "_blank"
              )
            }
          >
            Space-Track
          </button>
          <button
            className="os-chrome-btn"
            onClick={() =>
              window.open(`https://n2yo.com/satellite/?s=${clickedSatId}`, "_blank")
            }
          >
            N2YO
          </button>
        </div>
      </div>
    </div>
  );
}
