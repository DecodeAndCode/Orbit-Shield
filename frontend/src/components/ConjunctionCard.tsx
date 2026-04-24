import type { ConjunctionResponse } from "../api/types";

function riskColor(pc: number | null): string {
  if (pc === null) return "var(--os-fg3)";
  if (pc >= 1e-4) return "var(--os-risk-high)";
  if (pc >= 1e-6) return "var(--os-risk-medium)";
  return "var(--os-risk-low)";
}

function formatPc(pc: number | null): string {
  if (pc === null) return "N/A";
  return pc.toExponential(2);
}

function timeUntil(tca: string): string {
  const diff = new Date(tca).getTime() - Date.now();
  if (diff < 0) return "PASSED";
  const hours = Math.floor(diff / 3_600_000);
  const mins = Math.floor((diff % 3_600_000) / 60_000);
  if (hours > 24) return `${Math.floor(hours / 24)}d ${hours % 24}h`;
  return `${hours}h ${mins}m`;
}

interface Props {
  conjunction: ConjunctionResponse;
  selected: boolean;
  onClick: () => void;
}

export default function ConjunctionCard({
  conjunction: c,
  selected,
  onClick,
}: Props) {
  const effectivePc = c.pc_ml ?? c.pc_classical;
  const color = riskColor(effectivePc);
  const hasMl = c.pc_ml !== null;

  return (
    <div
      onClick={onClick}
      className={`os-conj ${selected ? "is-selected" : ""}`}
    >
      <div className="os-conj-bar" style={{ background: color }} />
      <div className="os-conj-top">
        <div className="os-conj-names">
          <span>{c.primary_name || `#${c.primary_norad_id}`}</span>
          <span className="os-conj-x">×</span>
          <span>{c.secondary_name || `#${c.secondary_norad_id}`}</span>
        </div>
        <div className="os-conj-pc">
          <span className="mono" style={{ color }}>
            {formatPc(effectivePc)}
          </span>
          {hasMl && <span className="os-ml-tag">ML</span>}
        </div>
      </div>
      <div className="os-conj-meta mono">
        <span>
          {c.miss_distance_km !== null
            ? `${c.miss_distance_km.toFixed(3)} km`
            : "—"}
        </span>
        <span>{timeUntil(c.tca)}</span>
      </div>
    </div>
  );
}
