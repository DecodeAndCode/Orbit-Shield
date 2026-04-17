import { useConjunctions } from "../api/client";
import { useColliderStore } from "../stores/colliderStore";
import ConjunctionCard from "./ConjunctionCard";

export default function ConjunctionTimeline() {
  const { data: conjunctions, isLoading, error } = useConjunctions();
  const selectedId = useColliderStore((s) => s.selectedConjunctionId);
  const select = useColliderStore((s) => s.selectConjunction);

  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b border-[var(--color-border)]">
        <h2 className="text-sm font-semibold tracking-wide uppercase text-[var(--color-text-secondary)]">
          Conjunctions
        </h2>
        <p className="text-xs text-[var(--color-text-secondary)] mt-0.5">
          Sorted by collision probability
        </p>
      </div>

      <div className="flex-1 overflow-y-auto">
        {isLoading && (
          <div className="p-4 text-sm text-[var(--color-text-secondary)]">
            Loading...
          </div>
        )}
        {error && (
          <div className="p-4 text-sm text-[var(--color-risk-high)]">
            Failed to load conjunctions
          </div>
        )}
        {conjunctions?.map((c) => (
          <ConjunctionCard
            key={c.id}
            conjunction={c}
            selected={c.id === selectedId}
            onClick={() => select(c.id)}
          />
        ))}
        {conjunctions && conjunctions.length === 0 && (
          <div className="p-4 text-sm text-[var(--color-text-secondary)]">
            No upcoming conjunctions
          </div>
        )}
      </div>
    </div>
  );
}
