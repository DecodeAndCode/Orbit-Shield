import { useEffect, useState } from "react";
import { useColliderStore, altKmToRegime } from "../stores/colliderStore";
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
  LEO: "#22d3ee",
  MEO: "#fb923c",
  GEO: "#c084fc",
  HEO: "#f472b6",
};

export default function SatDetailCard() {
  const clickedSatId = useColliderStore((s) => s.clickedSatId);
  const setClickedSat = useColliderStore((s) => s.setClickedSat);
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
  const regimeColor = regimeColors[regime] ?? "#22d3ee";

  const status = meta?.object_type === "DEBRIS" ? "DEBRIS" : "ACTIVE";
  const statusColor =
    status === "DEBRIS" ? "#ef4444" : "#22c55e";

  return (
    <div className="absolute top-3 right-3 z-40 w-80 bg-[var(--color-bg-card)]/95 backdrop-blur-md border border-[var(--color-border-strong)] rounded-lg shadow-2xl overflow-hidden">
      {/* Header bar */}
      <div
        className="h-1 w-full"
        style={{ backgroundColor: regimeColor }}
      />

      <div className="p-4">
        {/* Title row */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="min-w-0 flex-1">
            <div className="text-base font-bold text-[var(--color-text-primary)] truncate">
              {loading
                ? "Loading…"
                : meta?.name || `Object #${clickedSatId}`}
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span
                className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded"
                style={{
                  color: statusColor,
                  backgroundColor: statusColor + "22",
                }}
              >
                {status}
              </span>
              <span
                className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded"
                style={{
                  color: regimeColor,
                  backgroundColor: regimeColor + "22",
                }}
              >
                {regime}
              </span>
            </div>
          </div>
          <button
            onClick={() => setClickedSat(null)}
            className="flex-shrink-0 w-6 h-6 rounded hover:bg-[var(--color-bg-elevated)] text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] transition-colors flex items-center justify-center"
            aria-label="Close"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* NORAD + source */}
        <div className="mb-3 pb-3 border-b border-[var(--color-border)]">
          <div className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
            NORAD ID
          </div>
          <div className="text-sm mono text-[var(--color-text-primary)]">
            {clickedSatId}
          </div>
          <div className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)] mt-2">
            Source
          </div>
          <div className="text-xs mono text-[var(--color-accent)]">
            SPACE-TRACK
          </div>
        </div>

        {/* Details grid */}
        <div className="grid grid-cols-2 gap-x-3 gap-y-2 text-[11px]">
          <Field label="Type" value={meta?.object_type ?? "—"} mono />
          <Field label="Country" value={meta?.country ?? "—"} />
          <Field
            label="Perigee"
            value={perigee !== null ? `${perigee.toFixed(1)} km` : "—"}
            mono
          />
          <Field
            label="Apogee"
            value={apogee !== null ? `${apogee.toFixed(1)} km` : "—"}
            mono
          />
          <Field
            label="Inclination"
            value={
              meta?.inclination !== null && meta?.inclination !== undefined
                ? `${meta.inclination.toFixed(2)}°`
                : "—"
            }
            mono
          />
          <Field label="RCS" value={meta?.rcs_size ?? "—"} mono />
          <Field
            label="Launch"
            value={
              meta?.launch_date
                ? new Date(meta.launch_date).toISOString().slice(0, 10)
                : "—"
            }
            mono
          />
          <Field label="Regime" value={regime} mono />
        </div>

        {/* Actions */}
        <div className="mt-3 pt-3 border-t border-[var(--color-border)] flex items-center gap-2">
          <button
            className="flex-1 px-2 py-1.5 text-[10px] uppercase tracking-wider rounded bg-[var(--color-bg-elevated)] border border-[var(--color-border)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] transition-colors"
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
            className="flex-1 px-2 py-1.5 text-[10px] uppercase tracking-wider rounded bg-[var(--color-bg-elevated)] border border-[var(--color-border)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] transition-colors"
            onClick={() =>
              window.open(
                `https://n2yo.com/satellite/?s=${clickedSatId}`,
                "_blank"
              )
            }
          >
            N2YO
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <>
      <span className="text-[var(--color-text-muted)]">{label}</span>
      <span
        className={`text-[var(--color-text-primary)] text-right ${
          mono ? "mono tabular" : ""
        } truncate`}
      >
        {value}
      </span>
    </>
  );
}
