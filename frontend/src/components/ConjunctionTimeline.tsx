import { useMemo } from "react";
import { useConjunctions } from "../api/client";
import { useOrbitShieldStore, pcToRiskLevel } from "../stores/orbitShieldStore";
import ConjunctionCard from "./ConjunctionCard";

export default function ConjunctionTimeline() {
  const hoursAhead = useOrbitShieldStore((s) => s.hoursAhead);
  const minPc = useOrbitShieldStore((s) => s.minPc);
  const activeRisks = useOrbitShieldStore((s) => s.riskLevels);
  const selectedId = useOrbitShieldStore((s) => s.selectedConjunctionId);
  const select = useOrbitShieldStore((s) => s.selectConjunction);

  const { data, isLoading, error } = useConjunctions(
    minPc ?? undefined,
    hoursAhead
  );

  const filtered = useMemo(() => {
    if (!data) return [];
    return data.filter((c) => {
      const pc = c.pc_ml ?? c.pc_classical ?? null;
      return activeRisks.has(pcToRiskLevel(pc));
    });
  }, [data, activeRisks]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-[0.15em] text-[var(--color-text-primary)]">
            Conjunctions
          </h2>
          <p className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
            Sorted by Pc · next {hoursAhead}h
          </p>
        </div>
        <div className="px-2 py-0.5 rounded bg-[var(--color-bg-card)] text-[10px] mono tabular text-[var(--color-text-secondary)]">
          {filtered.length}/{data?.length ?? 0}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {isLoading && (
          <div className="p-4 text-xs text-[var(--color-text-muted)]">
            Loading conjunctions…
          </div>
        )}
        {error && (
          <div className="p-4 text-xs text-[var(--color-risk-high)]">
            Failed to load conjunctions
          </div>
        )}
        {filtered.map((c) => (
          <ConjunctionCard
            key={c.id}
            conjunction={c}
            selected={c.id === selectedId}
            onClick={() => select(c.id)}
          />
        ))}
        {!isLoading && filtered.length === 0 && (
          <div className="p-6 text-xs text-[var(--color-text-muted)] text-center">
            No events match current filters
          </div>
        )}
      </div>
    </div>
  );
}
