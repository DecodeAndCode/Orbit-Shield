import { useState } from "react";
import { useSatellites } from "../api/client";
import { useOrbitShieldStore } from "../stores/orbitShieldStore";
import StatsBar from "./StatsBar";

export default function Header() {
  const [search, setSearch] = useState("");
  const { data } = useSatellites(search || undefined);
  const setAlertModalOpen = useOrbitShieldStore((s) => s.setAlertModalOpen);
  const setFilterDrawerOpen = useOrbitShieldStore((s) => s.setFilterDrawerOpen);
  const focusOnSat = useOrbitShieldStore((s) => s.focusOnSat);

  return (
    <header className="os-header">
      <div className="os-header-left">
        <button
          className="os-icon-btn mobile-only"
          onClick={() => setFilterDrawerOpen(true)}
          aria-label="Open filters"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="12" x2="15" y2="12" />
            <line x1="3" y1="18" x2="9" y2="18" />
          </svg>
        </button>
        <span className="os-brand">ORBIT-SHIELD</span>
        <span className="os-tagline">Space Situational Awareness</span>
      </div>

      <div className="os-search" style={{ position: "relative" }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input
          type="text"
          placeholder="Search objects, NORAD ID, or constellation…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {search && data?.items && data.items.length > 0 && (
          <div
            style={{
              position: "absolute",
              top: "calc(100% + 4px)",
              left: 0,
              right: 0,
              background: "var(--os-bg-card)",
              border: "1px solid var(--os-border-subtle)",
              borderRadius: 4,
              maxHeight: 280,
              overflowY: "auto",
              zIndex: 60,
              boxShadow: "var(--os-shadow-overlay)",
            }}
          >
            {data.items.slice(0, 10).map((sat) => (
              <button
                key={sat.norad_id}
                onClick={() => {
                  focusOnSat(sat.norad_id);
                  setSearch("");
                }}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  width: "100%",
                  padding: "8px 12px",
                  background: "transparent",
                  border: 0,
                  borderBottom: "1px solid var(--os-border-subtle)",
                  color: "var(--os-fg1)",
                  fontSize: 12,
                  cursor: "pointer",
                  textAlign: "left",
                }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.background = "var(--os-bg-elevated)")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.background = "transparent")
                }
              >
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {sat.name}
                </span>
                <span className="mono" style={{ color: "var(--os-fg3)", marginLeft: 8, flexShrink: 0 }}>
                  #{sat.norad_id}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="os-header-right">
        <StatsBar />
        <button className="os-chrome-btn" onClick={() => setAlertModalOpen(true)}>
          Alerts
        </button>
        <div className="os-live">
          <span className="os-dot-green" />
          Live
        </div>
      </div>
    </header>
  );
}
