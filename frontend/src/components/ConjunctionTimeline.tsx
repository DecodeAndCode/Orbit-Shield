import { useMemo, useEffect } from "react";
import { useConjunctions } from "../api/client";
import { useOrbitShieldStore, pcToRiskLevel } from "../stores/orbitShieldStore";
import ConjunctionCard from "./ConjunctionCard";

export default function ConjunctionTimeline() {
  const hoursAhead = useOrbitShieldStore((s) => s.hoursAhead);
  const minPc = useOrbitShieldStore((s) => s.minPc);
  const activeRisks = useOrbitShieldStore((s) => s.riskLevels);
  const selectedId = useOrbitShieldStore((s) => s.selectedConjunctionId);
  const select = useOrbitShieldStore((s) => s.selectConjunction);
  const timelineExpanded = useOrbitShieldStore((s) => s.timelineExpanded);
  const setTimelineExpanded = useOrbitShieldStore((s) => s.setTimelineExpanded);

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

  // Auto-select first conjunction on initial load
  useEffect(() => {
    if (filtered.length > 0 && !selectedId) {
      select(filtered[0].id);
    }
  }, [filtered, selectedId, select]);

  return (
    <>
      <div className="os-panel-head os-timeline-head">
        <div>
          <h2>Conjunctions</h2>
          <p>Sorted by Pc · next {hoursAhead}h</p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className="os-counter">
            {filtered.length}/{data?.length ?? 0}
          </span>
          <button
            className="os-icon-btn mobile-only"
            onClick={() => setTimelineExpanded(!timelineExpanded)}
            aria-label={timelineExpanded ? "Collapse timeline" : "Expand timeline"}
            style={{ padding: 6 }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              {timelineExpanded ? (
                <polyline points="18 15 12 9 6 15" />
              ) : (
                <polyline points="6 9 12 15 18 9" />
              )}
            </svg>
          </button>
        </div>
      </div>

      <div className={`os-timeline-body ${timelineExpanded ? "is-expanded" : ""}`}>
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
