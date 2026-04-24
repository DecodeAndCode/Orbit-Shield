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
    <>
      <div className="os-panel-head os-timeline-head">
        <div>
          <h2>Conjunctions</h2>
          <p>Sorted by Pc · next {hoursAhead}h</p>
        </div>
        <span className="os-counter">
          {filtered.length}/{data?.length ?? 0}
        </span>
      </div>

      <div className="os-timeline-body">
        {isLoading && (
          <div className="os-detail-empty">Loading conjunctions…</div>
        )}
        {error && (
          <div className="os-detail-empty" style={{ color: "var(--os-risk-high)" }}>
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
        {!isLoading && filtered.length === 0 && !error && (
          <div className="os-detail-empty">
            No events match current filters
          </div>
        )}
      </div>
    </>
  );
}
