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

function riskColor(label: string): string {
  if (label === "high") return "var(--os-risk-high)";
  if (label === "medium") return "var(--os-risk-medium)";
  return "var(--os-risk-low)";
}

function Field({
  k,
  v,
}: {
  k: string;
  v: string;
}) {
  return (
    <div>
      <div className="os-field-label">{k}</div>
      <div className="os-field-value mono">{v}</div>
    </div>
  );
}

export default function EventDetailPanel() {
  const selectedId = useOrbitShieldStore((s) => s.selectedConjunctionId);
  const { data: detail, isLoading } = useConjunctionDetail(selectedId);
  const { data: mlData } = useMLCompare(selectedId);

  if (!selectedId) {
    return (
      <div className="os-detail-empty">Select a conjunction to view details</div>
    );
  }

  if (isLoading) {
    return <div className="os-detail-empty">Loading…</div>;
  }

  if (!detail) return null;

  const rLabel = mlData?.risk_label ?? "low";
  const rColor = riskColor(rLabel);
  const pc = detail.pc_ml ?? detail.pc_classical;

  return (
    <div className="os-detail">
      <div className="os-detail-col">
        <div className="os-detail-title-row">
          <h3>
            {detail.primary_name || `#${detail.primary_norad_id}`} vs{" "}
            {detail.secondary_name || `#${detail.secondary_norad_id}`}
          </h3>
          <span
            className="os-risk-badge"
            style={{ color: rColor, background: `${rColor}22` }}
          >
            {rLabel.toUpperCase()}
          </span>
        </div>

        <div className="os-detail-grid">
          <Field k="TCA" v={formatDate(detail.tca)} />
          <Field
            k="Miss Distance"
            v={
              detail.miss_distance_km !== null
                ? `${detail.miss_distance_km.toFixed(3)} km`
                : "—"
            }
          />
          <Field
            k="Rel. Velocity"
            v={
              detail.relative_velocity_kms !== null
                ? `${detail.relative_velocity_kms.toFixed(2)} km/s`
                : "—"
            }
          />
          <Field
            k="Classical Pc"
            v={
              detail.pc_classical !== null
                ? detail.pc_classical.toExponential(2)
                : "—"
            }
          />
          <Field
            k="ML Pc"
            v={detail.pc_ml !== null ? detail.pc_ml.toExponential(2) : "—"}
          />
          <Field k="Effective Pc" v={pc !== null ? pc.toExponential(2) : "—"} />
        </div>

        {detail.cdm_history.length > 0 && (
          <div className="os-detail-cdm">
            <h4>CDM History ({detail.cdm_history.length})</h4>
            <div style={{ maxHeight: 100, overflowY: "auto" }}>
              {detail.cdm_history.map((cdm) => (
                <div key={cdm.id} className="os-cdm-row mono">
                  <span>
                    {cdm.cdm_timestamp ? formatDate(cdm.cdm_timestamp) : "—"}
                  </span>
                  <span>{cdm.pc ? cdm.pc.toExponential(2) : "—"}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="os-detail-col">
        {mlData && <PcComparisonChart data={mlData} />}
      </div>
    </div>
  );
}
