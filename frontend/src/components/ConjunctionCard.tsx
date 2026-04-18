import type { ConjunctionResponse } from "../api/types";

function riskColor(pc: number | null): string {
  if (pc === null) return "var(--color-text-muted)";
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
      className={`px-3 py-2.5 mx-2 my-1 rounded cursor-pointer border transition-all ${
        selected
          ? "border-[var(--color-accent)] bg-[var(--color-bg-elevated)]"
          : "border-transparent hover:bg-[var(--color-bg-card)] hover:border-[var(--color-border)]"
      }`}
    >
      <div className="flex justify-between items-start gap-2">
        <div className="text-xs font-medium text-[var(--color-text-primary)] truncate">
          <span className="truncate">
            {c.primary_name || `#${c.primary_norad_id}`}
          </span>
          <span className="text-[var(--color-text-muted)] mx-1">×</span>
          <span className="truncate">
            {c.secondary_name || `#${c.secondary_norad_id}`}
          </span>
        </div>
        <div className="flex flex-col items-end flex-shrink-0">
          <span
            className="text-[11px] mono tabular font-semibold"
            style={{ color }}
          >
            {formatPc(effectivePc)}
          </span>
          {hasMl && (
            <span className="text-[8px] uppercase tracking-wider text-[var(--color-accent)]">
              ML
            </span>
          )}
        </div>
      </div>
      <div className="flex justify-between mt-1.5 text-[10px] text-[var(--color-text-muted)] mono tabular">
        <span>
          {c.miss_distance_km !== null
            ? `${c.miss_distance_km.toFixed(3)} km`
            : "—"}
        </span>
        <span>{timeUntil(c.tca)}</span>
      </div>
      <div
        className="mt-2 h-[2px] rounded-full"
        style={{ backgroundColor: color, opacity: 0.7 }}
      />
    </div>
  );
}
