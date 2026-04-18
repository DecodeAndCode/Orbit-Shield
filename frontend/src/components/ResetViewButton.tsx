import { useColliderStore } from "../stores/colliderStore";

export default function ResetViewButton() {
  const focusNoradId = useColliderStore((s) => s.focusNoradId);
  const clickedSatId = useColliderStore((s) => s.clickedSatId);
  const focusOnSat = useColliderStore((s) => s.focusOnSat);
  const setClickedSat = useColliderStore((s) => s.setClickedSat);

  const hasSelection = focusNoradId !== null || clickedSatId !== null;
  if (!hasSelection) return null;

  return (
    <button
      onClick={() => {
        focusOnSat(null);
        setClickedSat(null);
      }}
      className="absolute bottom-3 right-3 z-40 flex items-center gap-1.5 px-3 py-1.5 text-[10px] uppercase tracking-[0.15em] rounded bg-[var(--color-bg-card)]/90 backdrop-blur-sm border border-[var(--color-border-strong)] text-[var(--color-text-secondary)] hover:text-[var(--color-accent)] hover:border-[var(--color-accent)] transition-colors shadow-lg"
      aria-label="Reset view"
    >
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <polyline points="1 4 1 10 7 10" />
        <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
      </svg>
      Reset View
    </button>
  );
}
