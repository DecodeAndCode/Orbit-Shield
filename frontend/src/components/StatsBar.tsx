import { useConjunctions, useCatalogPositions } from "../api/client";

function Stat({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div className="flex flex-col items-start px-3 lg:px-4 py-1 border-l border-[var(--color-border)] first:border-l-0">
      <span className="text-[9px] uppercase tracking-[0.15em] text-[var(--color-text-muted)]">
        {label}
      </span>
      <span
        className="text-sm font-semibold mono tabular"
        style={{ color: accent ?? "var(--color-text-primary)" }}
      >
        {value}
      </span>
    </div>
  );
}

export default function StatsBar() {
  const { data: conjunctions } = useConjunctions();
  const { data: catalog } = useCatalogPositions();

  const high = conjunctions?.filter(
    (c) => (c.pc_ml ?? c.pc_classical ?? 0) >= 1e-4
  ).length ?? 0;
  const med = conjunctions?.filter((c) => {
    const pc = c.pc_ml ?? c.pc_classical ?? 0;
    return pc >= 1e-6 && pc < 1e-4;
  }).length ?? 0;
  const low = conjunctions?.filter((c) => {
    const pc = c.pc_ml ?? c.pc_classical ?? 0;
    return pc < 1e-6;
  }).length ?? 0;

  return (
    <div className="hidden md:flex items-center bg-[var(--color-bg-secondary)]">
      <Stat label="Tracked" value={String(catalog?.count ?? "—")} />
      <Stat
        label="Conjunctions"
        value={String(conjunctions?.length ?? "—")}
      />
      <Stat label="High" value={String(high)} accent="var(--color-risk-high)" />
      <Stat
        label="Medium"
        value={String(med)}
        accent="var(--color-risk-medium)"
      />
      <Stat label="Low" value={String(low)} accent="var(--color-risk-low)" />
    </div>
  );
}
