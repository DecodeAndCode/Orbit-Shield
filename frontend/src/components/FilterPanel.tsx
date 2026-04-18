import {
  useColliderStore,
  type Regime,
  type ObjectType,
  type RiskLevel,
} from "../stores/colliderStore";

const REGIMES: { key: Regime; label: string; desc: string; color: string }[] = [
  { key: "LEO", label: "LEO", desc: "< 2,000 km", color: "var(--color-regime-leo)" },
  { key: "MEO", label: "MEO", desc: "2,000–35,000 km", color: "var(--color-regime-meo)" },
  { key: "GEO", label: "GEO", desc: "~35,786 km", color: "var(--color-regime-geo)" },
  { key: "HEO", label: "HEO", desc: "> 36,500 km", color: "#f472b6" },
];

const TYPES: { key: ObjectType; label: string }[] = [
  { key: "PAYLOAD", label: "Payload" },
  { key: "DEBRIS", label: "Debris" },
  { key: "ROCKET BODY", label: "Rocket Body" },
  { key: "UNKNOWN", label: "Unknown" },
];

const RISKS: { key: RiskLevel; label: string; pc: string; color: string }[] = [
  { key: "high", label: "High", pc: "≥ 1e-4", color: "var(--color-risk-high)" },
  { key: "medium", label: "Medium", pc: "≥ 1e-6", color: "var(--color-risk-medium)" },
  { key: "low", label: "Low", pc: "< 1e-6", color: "var(--color-risk-low)" },
];

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-5">
      <h3 className="text-[10px] font-semibold uppercase tracking-[0.15em] text-[var(--color-text-muted)] mb-2 px-1">
        {title}
      </h3>
      <div className="space-y-1">{children}</div>
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
      className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded text-xs transition-colors text-left ${
        active
          ? "bg-[var(--color-bg-elevated)] text-[var(--color-text-primary)]"
          : "text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-card)]"
      }`}
    >
      <div className="flex items-center gap-2">
        {dot && (
          <span
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: dot, opacity: active ? 1 : 0.3 }}
          />
        )}
        {children}
      </div>
      <span
        className={`w-3.5 h-3.5 rounded border flex items-center justify-center ${
          active
            ? "bg-[var(--color-accent)] border-[var(--color-accent)]"
            : "border-[var(--color-border-strong)]"
        }`}
      >
        {active && (
          <svg width="8" height="8" viewBox="0 0 10 10" fill="none">
            <path
              d="M1 5L4 8L9 2"
              stroke="#000"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        )}
      </span>
    </button>
  );
}

export default function FilterPanel() {
  const s = useColliderStore();

  return (
    <div className="h-full flex flex-col bg-[var(--color-bg-secondary)] border-r border-[var(--color-border)]">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
        <h2 className="text-xs font-semibold uppercase tracking-[0.15em] text-[var(--color-text-primary)]">
          Filters
        </h2>
        <button
          onClick={s.resetFilters}
          className="text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-accent)] uppercase tracking-wider"
        >
          Reset
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-4">
        <Section title="Orbit Regime">
          {REGIMES.map((r) => (
            <Toggle
              key={r.key}
              active={s.regimes.has(r.key)}
              onClick={() => s.toggleRegime(r.key)}
              dot={r.color}
            >
              <span className="font-medium">{r.label}</span>
              <span className="ml-2 text-[10px] text-[var(--color-text-muted)]">
                {r.desc}
              </span>
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
              {t.label}
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
              <span className="font-medium">{r.label}</span>
              <span className="ml-2 text-[10px] text-[var(--color-text-muted)] mono">
                Pc {r.pc}
              </span>
            </Toggle>
          ))}
        </Section>

        <Section title="Time Window">
          <div className="px-1 py-2">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-[var(--color-text-secondary)]">
                Hours ahead
              </span>
              <span className="text-xs mono text-[var(--color-text-primary)]">
                {s.hoursAhead}h
              </span>
            </div>
            <input
              type="range"
              min={6}
              max={168}
              step={6}
              value={s.hoursAhead}
              onChange={(e) => s.setHoursAhead(Number(e.target.value))}
              className="w-full accent-[var(--color-accent)]"
            />
            <div className="flex justify-between text-[9px] text-[var(--color-text-muted)] mt-1">
              <span>6h</span>
              <span>72h</span>
              <span>7d</span>
            </div>
          </div>
        </Section>

        <Section title="Minimum Pc">
          <div className="px-1">
            <select
              value={s.minPc === null ? "" : String(s.minPc)}
              onChange={(e) =>
                s.setMinPc(e.target.value === "" ? null : Number(e.target.value))
              }
              className="w-full bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded px-2 py-1.5 text-xs text-[var(--color-text-primary)] focus:outline-none focus:border-[var(--color-accent)]"
            >
              <option value="">Any</option>
              <option value={String(1e-8)}>≥ 1e-8</option>
              <option value={String(1e-6)}>≥ 1e-6 (Medium)</option>
              <option value={String(1e-4)}>≥ 1e-4 (High)</option>
            </select>
          </div>
        </Section>

        <Section title="Layers">
          <Toggle
            active={s.showPointCloud}
            onClick={() => s.setShowPointCloud(!s.showPointCloud)}
          >
            Catalog point cloud
          </Toggle>
          <Toggle
            active={s.showOrbits}
            onClick={() => s.setShowOrbits(!s.showOrbits)}
          >
            Conjunction orbits
          </Toggle>
        </Section>
      </div>
    </div>
  );
}
