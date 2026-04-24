import type { MLCompareResponse } from "../api/types";

interface Props {
  data: MLCompareResponse;
}

/**
 * Horizontal bar chart comparing classical vs ML Pc on a log₁₀ scale
 * from -10 (safe) to 0 (certain). Pure CSS — no Recharts dependency
 * needed for this minimal HUD-style visual.
 */
export default function PcComparisonChart({ data }: Props) {
  const toPct = (pc: number | null) => {
    if (pc === null || pc <= 0) return 0;
    const log = Math.log10(pc);
    return Math.max(0, Math.min(100, ((log + 10) / 10) * 100));
  };

  const fmtPc = (pc: number | null) =>
    pc !== null ? pc.toExponential(2) : "N/A";

  return (
    <div className="os-chart">
      <div className="os-chart-head">
        <h4>Pc Comparison (log₁₀)</h4>
        {data.confidence !== null && (
          <span className="mono os-fg2" style={{ fontSize: 11 }}>
            Agreement {(data.confidence * 100).toFixed(0)}%
          </span>
        )}
      </div>
      <div className="os-chart-row">
        <span className="os-chart-label">Classical</span>
        <div className="os-chart-track">
          <div
            className="os-chart-bar"
            style={{ width: `${toPct(data.pc_classical)}%` }}
          />
        </div>
        <span className="os-chart-val mono">{fmtPc(data.pc_classical)}</span>
      </div>
      <div className="os-chart-row">
        <span className="os-chart-label">ML Enhanced</span>
        <div className="os-chart-track">
          <div
            className="os-chart-bar os-chart-bar-ml"
            style={{ width: `${toPct(data.pc_ml)}%` }}
          />
        </div>
        <span className="os-chart-val mono">{fmtPc(data.pc_ml)}</span>
      </div>
      <div className="os-chart-axis mono">
        <span>-10</span>
        <span>-8</span>
        <span>-6</span>
        <span>-4</span>
        <span>-2</span>
        <span>0</span>
      </div>
    </div>
  );
}
