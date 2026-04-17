import type { ConjunctionResponse } from "../api/types";

function riskColor(pc: number | null): string {
  if (pc === null) return "var(--color-text-secondary)";
  if (pc >= 1e-4) return "var(--color-risk-high)";
  if (pc >= 1e-6) return "var(--color-risk-medium)";
  return "var(--color-risk-low)";
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

export default function ConjunctionCard({ conjunction: c, selected, onClick }: Props) {
  const color = riskColor(c.pc_classical);

  return (
    <div
      onClick={onClick}
      className={`p-3 mx-2 my-1.5 rounded cursor-pointer border transition-colors ${
        selected
          ? "border-[var(--color-accent)] bg-[var(--color-bg-card)]"
          : "border-transparent hover:bg-[var(--color-bg-card)]"
      }`}
    >
      <div className="flex justify-between items-start">
        <div className="text-sm font-medium">
          {c.primary_name || `#${c.primary_norad_id}`}
          <span className="text-[var(--color-text-secondary)]"> vs </span>
          {c.secondary_name || `#${c.secondary_norad_id}`}
        </div>
        <span className="text-xs font-mono" style={{ color }}>
          {formatPc(c.pc_classical)}
        </span>
      </div>
      <div className="flex justify-between mt-1.5 text-xs text-[var(--color-text-secondary)]">
        <span>
          {c.miss_distance_km !== null
            ? `${c.miss_distance_km.toFixed(3)} km`
            : "—"}
        </span>
        <span>{timeUntil(c.tca)}</span>
      </div>
      <div
        className="mt-1.5 h-0.5 rounded-full"
        style={{ backgroundColor: color, opacity: 0.6 }}
      />
    </div>
  );
}
