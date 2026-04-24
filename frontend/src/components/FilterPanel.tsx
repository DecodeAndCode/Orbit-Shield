import {
  useOrbitShieldStore,
  type Regime,
  type ObjectType,
  type RiskLevel,
} from "../stores/orbitShieldStore";

const REGIMES: { key: Regime; label: string; desc: string; color: string }[] = [
  { key: "LEO", label: "LEO", desc: "< 2,000 km", color: "var(--os-regime-leo)" },
  { key: "MEO", label: "MEO", desc: "2k–35k km", color: "var(--os-regime-meo)" },
  { key: "GEO", label: "GEO", desc: "~35,786 km", color: "var(--os-regime-geo)" },
  { key: "HEO", label: "HEO", desc: "> 36,500 km", color: "var(--os-regime-heo)" },
];

const TYPES: { key: ObjectType; label: string }[] = [
  { key: "PAYLOAD", label: "Payload" },
  { key: "DEBRIS", label: "Debris" },
  { key: "ROCKET BODY", label: "Rocket Body" },
  { key: "UNKNOWN", label: "Unknown" },
];

const RISKS: { key: RiskLevel; label: string; pc: string; color: string }[] = [
  { key: "high", label: "High", pc: "≥ 1e-4", color: "var(--os-risk-high)" },
  { key: "medium", label: "Medium", pc: "≥ 1e-6", color: "var(--os-risk-medium)" },
  { key: "low", label: "Low", pc: "< 1e-6", color: "var(--os-risk-low)" },
];

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="os-section">
      <h3>{title}</h3>
      <div>{children}</div>
    </div>
  );
}

function Toggle({
  active,
  onClick,
  children,
  dot,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  dot?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`os-toggle ${active ? "is-active" : ""}`}
    >
      <span className="os-toggle-left">
        {dot && (
          <span
            className="os-toggle-dot"
            style={{ background: dot, opacity: active ? 1 : 0.3 }}
          />
        )}
        {children}
      </span>
      <span className={`os-check ${active ? "is-active" : ""}`}>
        {active && (
          <svg width="8" height="8" viewBox="0 0 10 10" fill="none">
            <path d="M1 5L4 8L9 2" stroke="#000" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        )}
      </span>
    </button>
  );
}

export default function FilterPanel() {
  const s = useOrbitShieldStore();

  return (
    <>
      <div className="os-panel-head">
        <div>
          <h2>Filters</h2>
        </div>
        <button className="os-link-btn" onClick={s.resetFilters}>
          Reset
        </button>
      </div>

      <div className="os-filter-body">
        <Section title="Orbit Regime">
          {REGIMES.map((r) => (
            <Toggle
              key={r.key}
              active={s.regimes.has(r.key)}
              onClick={() => s.toggleRegime(r.key)}
              dot={r.color}
            >
              <span className="os-toggle-name">{r.label}</span>
              <span className="os-toggle-desc">{r.desc}</span>
            </Toggle>
          ))}
        </Section>

        <Section title="Object Type">
          {TYPES.map((t) => (
            <Toggle
              key={t.key}
              active={s.objectTypes.has(t.key)}
              onClick={() => s.toggleObjectType(t.key)}
            >
              <span className="os-toggle-name">{t.label}</span>
            </Toggle>
          ))}
        </Section>

        <Section title="Risk Level">
          {RISKS.map((r) => (
            <Toggle
              key={r.key}
              active={s.riskLevels.has(r.key)}
              onClick={() => s.toggleRiskLevel(r.key)}
              dot={r.color}
            >
              <span className="os-toggle-name">{r.label}</span>
              <span className="os-toggle-desc mono">Pc {r.pc}</span>
            </Toggle>
          ))}
        </Section>

        <Section title="Time Window">
          <div className="os-slider-block">
            <div className="os-slider-head">
              <span>Hours ahead</span>
              <span className="mono">{s.hoursAhead}h</span>
            </div>
            <input
              type="range"
              min={6}
              max={168}
              step={6}
              value={s.hoursAhead}
              onChange={(e) => s.setHoursAhead(Number(e.target.value))}
            />
            <div className="os-slider-ticks">
              <span>6h</span>
              <span>72h</span>
              <span>7d</span>
            </div>
          </div>
        </Section>

        <Section title="Minimum Pc">
          <select
            className="os-select"
            value={s.minPc === null ? "" : String(s.minPc)}
            onChange={(e) =>
              s.setMinPc(e.target.value === "" ? null : Number(e.target.value))
            }
          >
            <option value="">Any</option>
            <option value={String(1e-8)}>≥ 1e-8</option>
            <option value={String(1e-6)}>≥ 1e-6 (Medium)</option>
            <option value={String(1e-4)}>≥ 1e-4 (High)</option>
          </select>
        </Section>

        <Section title="Layers">
          <Toggle
            active={s.showPointCloud}
            onClick={() => s.setShowPointCloud(!s.showPointCloud)}
          >
            <span className="os-toggle-name">Catalog point cloud</span>
          </Toggle>
          <Toggle
            active={s.showOrbits}
            onClick={() => s.setShowOrbits(!s.showOrbits)}
          >
            <span className="os-toggle-name">Conjunction orbits</span>
          </Toggle>
        </Section>
      </div>
    </>
  );
}
