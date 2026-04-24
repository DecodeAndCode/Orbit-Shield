import { useEffect } from "react";
import Header from "./components/Header";
import ConjunctionTimeline from "./components/ConjunctionTimeline";
import GlobeView from "./components/GlobeView";
import EventDetailPanel from "./components/EventDetailPanel";
import AlertConfigForm from "./components/AlertConfigForm";
import FilterPanel from "./components/FilterPanel";
import HoverTooltip from "./components/HoverTooltip";
import SatDetailCard from "./components/SatDetailCard";
import ResetViewButton from "./components/ResetViewButton";
import { useOrbitShieldStore } from "./stores/orbitShieldStore";

export default function App() {
  const filterDrawerOpen = useOrbitShieldStore((s) => s.filterDrawerOpen);
  const setFilterDrawerOpen = useOrbitShieldStore((s) => s.setFilterDrawerOpen);
  const detailCollapsed = useOrbitShieldStore((s) => s.detailCollapsed);
  const toggleDetail = useOrbitShieldStore((s) => s.toggleDetail);
  const selectedId = useOrbitShieldStore((s) => s.selectedConjunctionId);
  const setAlertOpen = useOrbitShieldStore((s) => s.setAlertModalOpen);
  const setClickedSat = useOrbitShieldStore((s) => s.setClickedSat);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setAlertOpen(false);
        setClickedSat(null);
        setFilterDrawerOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setAlertOpen, setClickedSat, setFilterDrawerOpen]);

  return (
    <div className="os-app">
      <Header />

      <div className="os-workspace">
        <div className={`os-filter ${filterDrawerOpen ? "open" : ""}`}>
          <FilterPanel />
        </div>

        <div className="os-stage">
          <GlobeView />
          <GlobeLegend />
          <HoverTooltip />
          <SatDetailCard />
          <ResetViewButton />

          <div className={`os-detail-drawer ${detailCollapsed ? "collapsed" : ""}`}>
            <div className="os-drawer-handle" onClick={toggleDetail}>
              <span>{selectedId ? `Event Detail · #${selectedId}` : "Event Detail"}</span>
              <svg className="os-drawer-chev" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </div>
            <EventDetailPanel />
          </div>
        </div>

        <div className="os-timeline">
          <ConjunctionTimeline />
        </div>
      </div>

      <AlertConfigForm />
    </div>
  );
}

function GlobeLegend() {
  return (
    <div className="os-legend">
      <div className="os-legend-title">Regime</div>
      <div className="os-legend-row"><span className="os-dot" style={{background:"var(--os-regime-leo)"}}/>LEO</div>
      <div className="os-legend-row"><span className="os-dot" style={{background:"var(--os-regime-meo)"}}/>MEO</div>
      <div className="os-legend-row"><span className="os-dot" style={{background:"var(--os-regime-geo)"}}/>GEO</div>
      <div className="os-legend-row"><span className="os-dot" style={{background:"var(--os-regime-heo)"}}/>HEO</div>
    </div>
  );
}
