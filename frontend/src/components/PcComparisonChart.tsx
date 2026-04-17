import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { MLCompareResponse } from "../api/types";

interface Props {
  data: MLCompareResponse;
}

export default function PcComparisonChart({ data }: Props) {
  const chartData = [
    {
      name: "Classical",
      pc: data.pc_classical ? Math.log10(data.pc_classical) : null,
      raw: data.pc_classical,
    },
    {
      name: "ML Enhanced",
      pc: data.pc_ml ? Math.log10(data.pc_ml) : null,
      raw: data.pc_ml,
    },
  ];

  return (
    <div>
      <div className="flex justify-between items-center mb-2">
        <h4 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase">
          Pc Comparison (log₁₀)
        </h4>
        {data.confidence !== null && (
          <span className="text-xs text-[var(--color-text-secondary)]">
            Agreement: {(data.confidence * 100).toFixed(0)}%
          </span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={120}>
        <BarChart data={chartData} layout="vertical">
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis
            type="number"
            domain={[-10, 0]}
            tick={{ fontSize: 10, fill: "var(--color-text-secondary)" }}
          />
          <YAxis
            dataKey="name"
            type="category"
            width={80}
            tick={{ fontSize: 10, fill: "var(--color-text-secondary)" }}
          />
          <Tooltip
            formatter={(_value, _name, item) => {
              const raw = (item as { payload?: { raw: number | null } })?.payload?.raw;
              return raw ? raw.toExponential(2) : "N/A";
            }}
            contentStyle={{
              backgroundColor: "var(--color-bg-card)",
              border: "1px solid var(--color-border)",
              fontSize: 12,
            }}
          />
          <Bar dataKey="pc" fill="var(--color-accent)" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
