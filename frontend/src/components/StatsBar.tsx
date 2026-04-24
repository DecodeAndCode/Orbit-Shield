import { useConjunctions, useCatalogPositions } from "../api/client";

function Stat({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="os-stat">
      <span className="os-stat-label">{label}</span>
      <span className="os-stat-value" style={{ color: color ?? "var(--os-fg1)" }}>
        {value}
      </span>
    </div>
  );
}

export default function StatsBar() {
  const { data: conjunctions } = useConjunctions();
  const { data: catalog } = useCatalogPositions();

  const high =
    conjunctions?.filter((c) => (c.pc_ml ?? c.pc_classical ?? 0) >= 1e-4)
      .length ?? 0;
  const med =
    conjunctions?.filter((c) => {
      const pc = c.pc_ml ?? c.pc_classical ?? 0;
      return pc >= 1e-6 && pc < 1e-4;
    }).length ?? 0;
  const low =
    conjunctions?.filter((c) => {
      const pc = c.pc_ml ?? c.pc_classical ?? 0;
      return pc < 1e-6;
    }).length ?? 0;

  const fmt = (n: number | undefined) =>
    n === undefined ? "—" : n.toLocaleString();

  return (
    <div className="os-stats">
      <Stat label="Tracked" value={fmt(catalog?.count)} />
      <Stat label="Conjunctions" value={fmt(conjunctions?.length)} />
      <Stat label="High" value={String(high)} color="var(--os-risk-high)" />
      <Stat label="Medium" value={String(med)} color="var(--os-risk-medium)" />
      <Stat label="Low" value={String(low)} color="var(--os-risk-low)" />
    </div>
  );
}
