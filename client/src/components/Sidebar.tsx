import { Map, BarChart3, Table2, Settings, Info, Layers, ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";
import type { Weights, Filters } from "../types";

interface WeightSliderProps {
  label: string;
  icon: string;
  factorKey: keyof Weights;
  value: number;
  onChange: (key: keyof Weights, val: number) => void;
  normalised: number;
  color: string;
}

function WeightSlider({ label, icon, factorKey, value, onChange, normalised, color }: WeightSliderProps) {
  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs font-medium" style={{ color: "hsl(var(--sidebar-foreground))" }}>
          {icon} {label}
        </span>
        <span
          className="text-xs font-mono font-bold tabular-nums px-1.5 py-0.5 rounded"
          style={{ background: `${color}22`, color }}
        >
          {Math.round(normalised * 100)}%
        </span>
      </div>
      <input
        type="range" min={0} max={10} step={1} value={value}
        onChange={(e) => onChange(factorKey, Number(e.target.value))}
        className="weight-slider"
        style={{ accentColor: color }}
        data-testid={`slider-${factorKey}`}
      />
      <div className="flex justify-between text-[10px] mt-0.5" style={{ color: "hsl(var(--sidebar-foreground) / 0.4)" }}>
        <span>0</span><span>5</span><span>10</span>
      </div>
    </div>
  );
}

interface SidebarProps {
  weights: Weights;
  filters: Filters;
  villages: string[];
  lulcNames: string[];
  onWeightChange: (key: keyof Weights, val: number) => void;
  onFilterChange: (key: keyof Filters, val: string | number) => void;
  activeSection: string;
  onSectionChange: (s: string) => void;
}

const FACTOR_CONFIG: Array<{ key: keyof Weights; label: string; icon: string; color: string; source: string }> = [
  { key: "slope",  label: "Slope",         icon: "⛰️",  color: "#64748b", source: "NASA SRTM" },
  { key: "lulc",   label: "Land Cover",    icon: "🗺️",  color: "#16a34a", source: "ESA WorldCover" },
  { key: "ghi",    label: "Solar GHI",     icon: "☀️",  color: "#d97706", source: "PVGIS ERA5" },
  { key: "power",  label: "Grid Access",   icon: "⚡",  color: "#0891b2", source: "OSM Power" },
  { key: "road",   label: "Road Access",   icon: "🛣️",  color: "#7c3aed", source: "OSM Roads" },
  { key: "temp",   label: "Temperature",   icon: "🌡️",  color: "#dc2626", source: "NASA POWER" },
];

export function Sidebar({
  weights, filters, villages, lulcNames,
  onWeightChange, onFilterChange, activeSection, onSectionChange,
}: SidebarProps) {
  const [filtersOpen, setFiltersOpen] = useState(true);
  const totalWeight = Object.values(weights).reduce((a, b) => a + b, 0) || 1;
  const normWeights = Object.fromEntries(
    Object.entries(weights).map(([k, v]) => [k, v / totalWeight])
  ) as Record<keyof Weights, number>;

  return (
    <aside className="dashboard-sidebar flex flex-col">
      {/* Logo + branding */}
      <div className="px-4 py-5 border-b" style={{ borderColor: "hsl(var(--sidebar-border))" }}>
        <div className="flex items-center gap-3 mb-1">
          {/* Custom SVG logo */}
          <svg viewBox="0 0 32 32" width="28" height="28" aria-label="Kallakurichi Suitability" fill="none">
            <rect width="32" height="32" rx="7" fill="hsl(var(--accent))" />
            <path d="M7 24 L16 8 L25 24" stroke="hsl(220 24% 14%)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
            <circle cx="16" cy="8" r="2.2" fill="hsl(220 24% 14%)" />
            <path d="M11 19 L21 19" stroke="hsl(220 24% 14%)" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <div>
            <div className="text-sm font-bold leading-tight" style={{ color: "hsl(var(--sidebar-accent-foreground))" }}>
              KLK Suitability
            </div>
            <div className="text-[10px] font-medium" style={{ color: "hsl(var(--sidebar-foreground) / 0.55)" }}>
              Auroville Consulting
            </div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="pt-3 pb-2">
        {[
          { id: "map",    label: "Suitability Map",   Icon: Map },
          { id: "charts", label: "Factor Analysis",   Icon: BarChart3 },
          { id: "table",  label: "Parcel Rankings",   Icon: Table2 },
          { id: "data",   label: "Data Sources",      Icon: Layers },
        ].map(({ id, label, Icon }) => (
          <button
            key={id}
            className={`nav-item w-full text-left${activeSection === id ? " active" : ""}`}
            onClick={() => onSectionChange(id)}
            data-testid={`nav-${id}`}
          >
            <Icon size={15} strokeWidth={2} />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      <div className="mx-4 my-1 h-px" style={{ background: "hsl(var(--sidebar-border))" }} />

      {/* Weight controls */}
      <div className="px-4 pt-3 pb-1 flex-1 overflow-y-auto overscroll-contain">
        <div className="flex items-center justify-between mb-3">
          <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "hsl(var(--sidebar-foreground) / 0.5)" }}>
            Factor Weights
          </span>
          <span className="text-[10px] px-1.5 py-0.5 rounded font-mono" style={{ background: "hsl(var(--accent) / 0.15)", color: "hsl(var(--accent))" }}>
            auto-norm
          </span>
        </div>

        {FACTOR_CONFIG.map(({ key, label, icon, color }) => (
          <WeightSlider
            key={key}
            factorKey={key}
            label={label}
            icon={icon}
            value={weights[key]}
            normalised={normWeights[key]}
            onChange={onWeightChange}
            color={color}
          />
        ))}

        {/* Weight viz bar */}
        <div className="mt-1 mb-4">
          <div className="h-2 rounded-full overflow-hidden flex">
            {FACTOR_CONFIG.map(({ key, color }) => (
              <div
                key={key}
                style={{
                  width: `${normWeights[key] * 100}%`,
                  background: color,
                  transition: "width 0.3s ease",
                }}
              />
            ))}
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1.5">
            {FACTOR_CONFIG.map(({ key, label, color }) => (
              <span key={key} className="text-[10px] flex items-center gap-1" style={{ color: "hsl(var(--sidebar-foreground) / 0.6)" }}>
                <span style={{ width: 6, height: 6, borderRadius: 2, background: color, display: "inline-block" }} />
                {label.split(" ")[0]}
              </span>
            ))}
          </div>
        </div>

        <div className="mx-0 my-1 h-px" style={{ background: "hsl(var(--sidebar-border))" }} />

        {/* Filters */}
        <button
          className="flex items-center justify-between w-full py-2 text-[11px] font-semibold uppercase tracking-wider"
          style={{ color: "hsl(var(--sidebar-foreground) / 0.5)" }}
          onClick={() => setFiltersOpen(!filtersOpen)}
        >
          <span>Filters</span>
          {filtersOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>

        {filtersOpen && (
          <div className="space-y-3 pb-4">
            <div>
              <label className="text-[11px] font-medium mb-1 block" style={{ color: "hsl(var(--sidebar-foreground) / 0.7)" }}>Village / Taluk</label>
              <select
                className="w-full text-xs rounded-md px-2 py-1.5 font-medium"
                style={{
                  background: "hsl(var(--sidebar-accent))",
                  color: "hsl(var(--sidebar-accent-foreground))",
                  border: "1px solid hsl(var(--sidebar-border))",
                }}
                value={filters.village}
                onChange={(e) => onFilterChange("village", e.target.value)}
                data-testid="filter-village"
              >
                <option value="All">All Villages</option>
                {villages.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            </div>

            <div>
              <label className="text-[11px] font-medium mb-1 block" style={{ color: "hsl(var(--sidebar-foreground) / 0.7)" }}>LULC Class</label>
              <select
                className="w-full text-xs rounded-md px-2 py-1.5 font-medium"
                style={{
                  background: "hsl(var(--sidebar-accent))",
                  color: "hsl(var(--sidebar-accent-foreground))",
                  border: "1px solid hsl(var(--sidebar-border))",
                }}
                value={filters.lulc_name}
                onChange={(e) => onFilterChange("lulc_name", e.target.value)}
                data-testid="filter-lulc"
              >
                <option value="All">All Classes</option>
                {lulcNames.map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>

            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="text-[11px] font-medium" style={{ color: "hsl(var(--sidebar-foreground) / 0.7)" }}>Max Slope</label>
                <span className="text-[11px] font-mono" style={{ color: "hsl(var(--accent))" }}>{filters.max_slope}°</span>
              </div>
              <input type="range" min={1} max={30} step={0.5} value={filters.max_slope}
                onChange={(e) => onFilterChange("max_slope", Number(e.target.value))}
                className="weight-slider" data-testid="filter-slope" />
            </div>

            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="text-[11px] font-medium" style={{ color: "hsl(var(--sidebar-foreground) / 0.7)" }}>Max Grid Dist.</label>
                <span className="text-[11px] font-mono" style={{ color: "hsl(var(--accent))" }}>{filters.max_power_dist} km</span>
              </div>
              <input type="range" min={1} max={30} step={1} value={filters.max_power_dist}
                onChange={(e) => onFilterChange("max_power_dist", Number(e.target.value))}
                className="weight-slider" data-testid="filter-power-dist" />
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t text-[10px]" style={{
        borderColor: "hsl(var(--sidebar-border))",
        color: "hsl(var(--sidebar-foreground) / 0.4)"
      }}>
        <div>Real data · No API keys</div>
        <div>ESA · NASA · PVGIS · OSM</div>
      </div>
    </aside>
  );
}
