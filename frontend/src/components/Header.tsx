import { useState } from "react";
import { useSatellites } from "../api/client";
import { useColliderStore } from "../stores/colliderStore";
import StatsBar from "./StatsBar";

export default function Header() {
  const [search, setSearch] = useState("");
  const { data } = useSatellites(search || undefined);
  const setAlertModalOpen = useColliderStore((s) => s.setAlertModalOpen);
  const setFilterDrawerOpen = useColliderStore((s) => s.setFilterDrawerOpen);
  const focusOnSat = useColliderStore((s) => s.focusOnSat);

  return (
    <header className="flex items-center justify-between px-3 md:px-4 h-12 bg-[var(--color-bg-secondary)] border-b border-[var(--color-border)] gap-3">
      {/* Left: brand + mobile filter */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => setFilterDrawerOpen(true)}
          className="lg:hidden p-1.5 rounded hover:bg-[var(--color-bg-card)] text-[var(--color-text-secondary)]"
          aria-label="Open filters"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="12" x2="15" y2="12" />
            <line x1="3" y1="18" x2="9" y2="18" />
          </svg>
        </button>
        <div className="flex items-baseline gap-2">
          <span className="text-base font-bold tracking-[0.15em] text-[var(--color-accent)]">
            COLLIDER
          </span>
          <span className="hidden md:inline text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
            Space Situational Awareness
          </span>
        </div>
      </div>

      {/* Center: search */}
      <div className="relative flex-1 max-w-md mx-2">
        <svg
          className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]"
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input
          type="text"
          placeholder="Search objects, NORAD ID, or constellation…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-8 pr-3 py-1.5 text-xs rounded bg-[var(--color-bg-primary)] border border-[var(--color-border)] text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] transition-colors"
        />
        {search && data?.items && data.items.length > 0 && (
          <div className="absolute top-full left-0 mt-1 w-full bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded shadow-xl z-50 max-h-64 overflow-y-auto">
            {data.items.slice(0, 10).map((sat) => (
              <div
                key={sat.norad_id}
                className="px-3 py-2 text-xs hover:bg-[var(--color-bg-elevated)] cursor-pointer flex items-center justify-between"
                onClick={() => {
                  focusOnSat(sat.norad_id);
                  setSearch("");
                }}
              >
                <span className="text-[var(--color-text-primary)] truncate">
                  {sat.name}
                </span>
                <span className="text-[var(--color-text-muted)] mono ml-2 flex-shrink-0">
                  #{sat.norad_id}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Right: stats + actions */}
      <div className="flex items-center gap-2">
        <StatsBar />
        <button
          onClick={() => setAlertModalOpen(true)}
          className="px-3 py-1.5 text-[11px] uppercase tracking-wider rounded bg-[var(--color-bg-card)] border border-[var(--color-border)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] transition-colors"
        >
          Alerts
        </button>
        <div className="hidden sm:flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-[var(--color-text-secondary)]">
          <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-risk-low)] animate-pulse" />
          Live
        </div>
      </div>
    </header>
  );
}
