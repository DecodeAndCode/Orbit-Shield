import { useOrbitShieldStore } from "../stores/orbitShieldStore";
import { useConjunctionDetail, useMLCompare } from "../api/client";
import PcComparisonChart from "./PcComparisonChart";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZoneName: "short",
  });
}

function riskBadge(label: string) {
  const colors: Record<string, string> = {
    low: "bg-green-900 text-green-300",
    medium: "bg-yellow-900 text-yellow-300",
    high: "bg-red-900 text-red-300",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[label] || ""}`}>
      {label.toUpperCase()}
    </span>
  );
}

export default function EventDetailPanel() {
  const selectedId = useOrbitShieldStore((s) => s.selectedConjunctionId);
  const { data: detail, isLoading } = useConjunctionDetail(selectedId);
  const { data: mlData } = useMLCompare(selectedId);

  if (!selectedId) {
    return (
      <div className="p-4 text-sm text-[var(--color-text-secondary)]">
        Select a conjunction to view details
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="p-4 text-sm text-[var(--color-text-secondary)]">Loading...</div>
    );
  }

  if (!detail) return null;

  return (
    <div className="p-4 grid grid-cols-2 gap-4">
      <div>
        <div className="flex items-center gap-2 mb-3">
          <h3 className="text-sm font-semibold">
            {detail.primary_name || `#${detail.primary_norad_id}`}
            {" vs "}
            {detail.secondary_name || `#${detail.secondary_norad_id}`}
          </h3>
          {mlData && riskBadge(mlData.risk_label)}
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <span className="text-[var(--color-text-secondary)]">TCA</span>
            <div>{formatDate(detail.tca)}</div>
          </div>
          <div>
            <span className="text-[var(--color-text-secondary)]">Miss Distance</span>
            <div>
              {detail.miss_distance_km !== null
                ? `${detail.miss_distance_km.toFixed(3)} km`
                : "—"}
            </div>
          </div>
          <div>
            <span className="text-[var(--color-text-secondary)]">Relative Velocity</span>
            <div>
              {detail.relative_velocity_kms !== null
                ? `${detail.relative_velocity_kms.toFixed(2)} km/s`
                : "—"}
            </div>
          </div>
          <div>
            <span className="text-[var(--color-text-secondary)]">Classical Pc</span>
            <div>
              {detail.pc_classical !== null
                ? detail.pc_classical.toExponential(2)
                : "—"}
            </div>
          </div>
        </div>

        {detail.cdm_history.length > 0 && (
          <div className="mt-3">
            <h4 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase mb-1">
              CDM History ({detail.cdm_history.length})
            </h4>
            <div className="max-h-20 overflow-y-auto text-xs space-y-0.5">
              {detail.cdm_history.map((cdm) => (
                <div key={cdm.id} className="flex justify-between">
                  <span>{cdm.cdm_timestamp ? formatDate(cdm.cdm_timestamp) : "—"}</span>
                  <span>{cdm.pc ? cdm.pc.toExponential(2) : "—"}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div>{mlData && <PcComparisonChart data={mlData} />}</div>
    </div>
  );
}
