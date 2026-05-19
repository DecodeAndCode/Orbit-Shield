import { useEffect, useRef, useState } from "react";
import { useSatellites } from "../api/client";
import { useOrbitShieldStore } from "../stores/orbitShieldStore";
import StatsBar from "./StatsBar";

function FilterIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="3" y1="6" x2="21" y2="6" />
      <line x1="3" y1="12" x2="15" y2="12" />
      <line x1="3" y1="18" x2="9" y2="18" />
    </svg>
  );
}

function SearchIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function BellIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}

export default function Header() {
  const [search, setSearch] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const { data } = useSatellites(search || undefined);
  const setAlertModalOpen = useOrbitShieldStore((s) => s.setAlertModalOpen);
  const filterDrawerOpen = useOrbitShieldStore((s) => s.filterDrawerOpen);
  const setFilterDrawerOpen = useOrbitShieldStore((s) => s.setFilterDrawerOpen);
  const focusOnSat = useOrbitShieldStore((s) => s.focusOnSat);
  const overlayRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!searchOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSearchOpen(false);
    };
    const onClickOutside = (e: MouseEvent) => {
      if (overlayRef.current && !overlayRef.current.contains(e.target as Node)) {
        const trigger = (e.target as HTMLElement).closest(".os-search-trigger");
        if (!trigger) setSearchOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onClickOutside);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onClickOutside);
    };
  }, [searchOpen]);

  const pick = (norad: number) => {
    focusOnSat(norad);
    setSearch("");
    setSearchOpen(false);
  };

  const onEnter = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && data?.items?.[0]) pick(data.items[0].norad_id);
  };

  const dropdown =
    search && data?.items && data.items.length > 0 ? (
      <ul className="os-search-results" role="listbox">
        {data.items.slice(0, 10).map((sat) => (
          <li key={sat.norad_id}>
            <button type="button" onClick={() => pick(sat.norad_id)}>
              <span className="os-search-result-name">{sat.name}</span>
              <span className="os-search-result-id mono">#{sat.norad_id}</span>
            </button>
          </li>
        ))}
      </ul>
    ) : null;

  return (
    <header className="os-header">
      <div className="os-header-left">
        <button
          type="button"
          className="os-icon-btn os-filter-toggle"
          onClick={() => setFilterDrawerOpen(!filterDrawerOpen)}
          aria-label="Toggle filters"
          aria-expanded={filterDrawerOpen}
        >
          <FilterIcon />
        </button>
        <div className="os-brand-block">
          <span className="os-brand">ORBIT-SHIELD</span>
          <span className="os-tagline">Space Situational Awareness</span>
        </div>
      </div>

      <div className="os-search os-search-inline">
        <SearchIcon />
        <input
          type="text"
          placeholder="Search objects, NORAD ID, or constellation…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={onEnter}
          aria-label="Search satellites"
        />
        {dropdown}
      </div>

      <div className="os-header-right">
        <StatsBar />
        <button
          type="button"
          className="os-icon-btn os-search-trigger"
          onClick={() => setSearchOpen((v) => !v)}
          aria-label={searchOpen ? "Close search" : "Open search"}
          aria-expanded={searchOpen}
        >
          {searchOpen ? <CloseIcon /> : <SearchIcon size={16} />}
        </button>
        <button
          type="button"
          className="os-chrome-btn os-alert-btn"
          onClick={() => setAlertModalOpen(true)}
          aria-label="Open alerts"
        >
          <BellIcon />
          <span className="os-alert-label">Alerts</span>
        </button>
        <div className="os-live" aria-label="Live data">
          <span className="os-dot-green" aria-hidden />
          <span className="os-live-label">Live</span>
        </div>
      </div>

      {searchOpen && (
        <div className="os-search os-search-overlay" ref={overlayRef} role="search">
          <SearchIcon />
          <input
            autoFocus
            type="text"
            placeholder="Search objects, NORAD ID, or constellation…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={onEnter}
            aria-label="Search satellites"
          />
          <button
            type="button"
            className="os-search-overlay-close"
            onClick={() => setSearchOpen(false)}
            aria-label="Close search"
          >
            <CloseIcon />
          </button>
          {dropdown}
        </div>
      )}
    </header>
  );
}
