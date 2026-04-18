import Header from "./components/Header";
import ConjunctionTimeline from "./components/ConjunctionTimeline";
import GlobeView from "./components/GlobeView";
import EventDetailPanel from "./components/EventDetailPanel";
import AlertConfigForm from "./components/AlertConfigForm";
import FilterPanel from "./components/FilterPanel";
import { useColliderStore } from "./stores/colliderStore";

export default function App() {
  const filterDrawerOpen = useColliderStore((s) => s.filterDrawerOpen);
  const setFilterDrawerOpen = useColliderStore((s) => s.setFilterDrawerOpen);
  const detailCollapsed = useColliderStore((s) => s.detailCollapsed);
  const toggleDetail = useColliderStore((s) => s.toggleDetail);
  const selectedId = useColliderStore((s) => s.selectedConjunctionId);

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-[var(--color-bg-primary)]">
      <Header />

      <div className="flex flex-1 overflow-hidden relative">
        {/* Left filter rail — desktop */}
        <aside className="hidden lg:flex w-64 xl:w-72 flex-shrink-0">
          <FilterPanel />
        </aside>

        {/* Mobile filter drawer */}
        {filterDrawerOpen && (
          <>
            <div
              className="lg:hidden fixed inset-0 bg-black/60 z-40"
              onClick={() => setFilterDrawerOpen(false)}
            />
            <aside className="lg:hidden fixed top-12 left-0 bottom-0 w-72 z-50 shadow-2xl">
              <FilterPanel />
            </aside>
          </>
        )}

        {/* Center: globe + bottom detail */}
        <main className="flex-1 flex flex-col overflow-hidden min-w-0 relative">
          <div className="flex-1 relative bg-[var(--color-bg-primary)]">
            <GlobeView />
            <GlobeLegend />
          </div>

          {/* Detail panel — collapsible */}
          <div
            className={`border-t border-[var(--color-border)] bg-[var(--color-bg-secondary)] transition-all duration-200 ${
              detailCollapsed ? "h-10" : "h-56 md:h-64"
            }`}
          >
            <button
              onClick={toggleDetail}
              className="w-full h-10 flex items-center justify-between px-4 text-[10px] uppercase tracking-[0.15em] text-[var(--color-text-secondary)] hover:text-[var(--color-accent)] transition-colors"
            >
              <span>
                {selectedId ? `Event Detail #${selectedId}` : "Event Detail"}
              </span>
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className={`transition-transform ${
                  detailCollapsed ? "rotate-180" : ""
                }`}
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>
            {!detailCollapsed && (
              <div className="h-[calc(100%-2.5rem)] overflow-y-auto">
                <EventDetailPanel />
              </div>
            )}
          </div>
        </main>

        {/* Right rail: conjunctions list */}
        <aside className="hidden md:flex w-72 xl:w-80 flex-shrink-0 border-l border-[var(--color-border)] bg-[var(--color-bg-secondary)] flex-col overflow-hidden">
          <ConjunctionTimeline />
        </aside>
      </div>

      <AlertConfigForm />
    </div>
  );
}

function GlobeLegend() {
  return (
    <div className="absolute bottom-3 left-3 bg-[var(--color-bg-card)]/80 backdrop-blur-sm border border-[var(--color-border)] rounded px-3 py-2 pointer-events-none">
      <div className="text-[9px] uppercase tracking-[0.15em] text-[var(--color-text-muted)] mb-1.5">
        Regime
      </div>
      <div className="flex flex-col gap-1 text-[10px]">
        <LegendItem color="#22d3ee" label="LEO" />
        <LegendItem color="#fb923c" label="MEO" />
        <LegendItem color="#c084fc" label="GEO" />
      </div>
    </div>
  );
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-2 text-[var(--color-text-secondary)]">
      <span
        className="w-2 h-2 rounded-full"
        style={{ backgroundColor: color }}
      />
      {label}
    </div>
  );
}
