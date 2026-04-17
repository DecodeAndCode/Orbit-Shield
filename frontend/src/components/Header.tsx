import { useState } from "react";
import { useSatellites } from "../api/client";
import { useColliderStore } from "../stores/colliderStore";

export default function Header() {
  const [search, setSearch] = useState("");
  const { data } = useSatellites(search || undefined);
  const setAlertModalOpen = useColliderStore((s) => s.setAlertModalOpen);

  return (
    <header className="flex items-center justify-between px-4 py-2 bg-[var(--color-bg-secondary)] border-b border-[var(--color-border)]">
      <div className="flex items-center gap-3">
        <div className="text-xl font-bold tracking-wide text-[var(--color-accent)]">
          COLLIDER
        </div>
        <span className="text-xs text-[var(--color-text-secondary)]">
          Collision Avoidance System
        </span>
      </div>

      <div className="relative">
        <input
          type="text"
          placeholder="Search satellites..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-64 px-3 py-1.5 text-sm rounded bg-[var(--color-bg-primary)] border border-[var(--color-border)] text-[var(--color-text-primary)] placeholder-[var(--color-text-secondary)] focus:outline-none focus:border-[var(--color-accent)]"
        />
        {search && data?.items && data.items.length > 0 && (
          <div className="absolute top-full left-0 mt-1 w-full bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded shadow-lg z-50 max-h-48 overflow-y-auto">
            {data.items.slice(0, 8).map((sat) => (
              <div
                key={sat.norad_id}
                className="px-3 py-1.5 text-sm hover:bg-[var(--color-bg-secondary)] cursor-pointer"
                onClick={() => setSearch("")}
              >
                <span className="text-[var(--color-text-primary)]">{sat.name}</span>
                <span className="ml-2 text-[var(--color-text-secondary)]">
                  #{sat.norad_id}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={() => setAlertModalOpen(true)}
          className="px-3 py-1.5 text-sm rounded bg-[var(--color-bg-card)] border border-[var(--color-border)] hover:border-[var(--color-accent)] transition-colors"
        >
          Alerts
        </button>
        <div className="flex items-center gap-1.5 text-xs text-[var(--color-text-secondary)]">
          <span className="w-2 h-2 rounded-full bg-[var(--color-risk-low)]" />
          Connected
        </div>
      </div>
    </header>
  );
}
