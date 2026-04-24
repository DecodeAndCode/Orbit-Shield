import { useOrbitShieldStore } from "../stores/orbitShieldStore";

export default function ResetViewButton() {
  const focusNoradId = useOrbitShieldStore((s) => s.focusNoradId);
  const clickedSatId = useOrbitShieldStore((s) => s.clickedSatId);
  const focusOnSat = useOrbitShieldStore((s) => s.focusOnSat);
  const setClickedSat = useOrbitShieldStore((s) => s.setClickedSat);

  const hasSelection = focusNoradId !== null || clickedSatId !== null;
  if (!hasSelection) return null;

  return (
    <button
      className="os-reset-btn"
      onClick={() => {
        focusOnSat(null);
        setClickedSat(null);
      }}
      aria-label="Reset view"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M3 12a9 9 0 1 0 3-6.7" />
        <path d="M3 4v5h5" />
      </svg>
      Reset View
    </button>
  );
}
