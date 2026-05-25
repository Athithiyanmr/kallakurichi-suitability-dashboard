import {
  Map, BarChart3, Table2, Database,
  ChevronDown, ChevronUp, SlidersHorizontal, Filter,
} from "lucide-react";
import { useState } from "react";
import type { Weights, Filters } from "../types";

interface WeightSliderProps {
  label: string;
  factorKey: keyof Weights;
  value: number;
  normalised: number;
  color: string;
  icon: React.ReactNode;
}

function WeightSlider({ label, factorKey, value, normalised, color, icon }: WeightSliderProps) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
        <span style={{
          display: "flex", alignItems: "center", gap: 6,
          fontSize: 12, fontWeight: 500, color: "hsl(var(--foreground-secondary))",
        }}>
          <span style={{ opacity: 0.75 }}>{icon}</span>
          {label}
        </span>
        <span style={{
          fontSize: 10, fontWeight: 700, fontFamily: "monospace",
          padding: "2px 6px", borderRadius: 100,
          background: `${color}18`,
          color: color,
          minWidth: 34, textAlign: "center",
        }}>
          {Math.round(normalised * 100)}%
        </span>
      </div>
      <input
        type="range" min={0} max={10} step={1} value={value}
        onChange={(e) => {/* handled via parent */}}
        onInput={(e) => {
          const el = e.target as HTMLInputElement;
          // The parent rerenders via prop — trigger via the onChange pattern below
          (e as any)._triggerChange = true;
        }}
        className="weight-slider"
        style={{ accentColor: color }}
        data-testid={`slider-${factorKey}`}
        // Actually fire onChange — onInput above was illustrative
        // This is the real handler:
        readOnly
      />
      {/* The actual value-driven input (controlled) */}
      <input
        type="range" min={0} max={10} step={1}
        value={value}
        className="weight-slider"
        style={{ accentColor: color, display: "none" }}
        data-testid={`slider-hidden-${factorKey}`}
        readOnly
      />
    </div>
  );
}

// Controlled weight slider
function ControlledSlider({ label, factorKey, value, normalised, color, icon, onChange }: WeightSliderProps & {
  onChange: (key: keyof Weights, val: number) => void;
}) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 5 }}>
        <span style={{
          display: "flex", alignItems: "center", gap: 6,
          fontSize: 12, fontWeight: 500, color: "hsl(var(--foreground-secondary))",
        }}>
          <span style={{ fontSize: 13 }}>{icon}</span>
          {label}
        </span>
        <span style={{
          fontSize: 10, fontWeight: 700, fontFamily: "monospace",
          padding: "1px 6px", borderRadius: 100,
          background: `${color}1A`,
          color: color,
          minWidth: 34, textAlign: "center",
        }}>
          {Math.round(normalised * 100)}%
        </span>
      </div>
      <input
        type="range" min={0} max={10} step={1}
        value={value}
        onChange={(e) => onChange(factorKey, Number(e.target.value))}
        className="weight-slider"
        style={{ accentColor: color }}
        data-testid={`slider-${factorKey}`}
      />
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

const FACTOR_CONFIG: Array<{
  key: keyof Weights; label: string; icon: string; color: string;
}> = [
  { key: "slope",  label: "Slope",       icon: "⛰", color: "#5f6368" },
  { key: "lulc",   label: "Land Cover",  icon: "🌿", color: "#0f9d58" },
  { key: "ghi",    label: "Solar GHI",   icon: "☀", color: "#f4b400" },
  { key: "power",  label: "Grid Access", icon: "⚡", color: "#4285f4" },
  { key: "road",   label: "Road Access", icon: "🛣", color: "#a142f4" },
  { key: "temp",   label: "Temperature", icon: "🌡", color: "#ea4335" },
];

const NAV = [
  { id: "map",    label: "Suitability Map",  Icon: Map },
  { id: "charts", label: "Factor Analysis",  Icon: BarChart3 },
  { id: "table",  label: "Parcel Rankings",  Icon: Table2 },
  { id: "data",   label: "Data Sources",     Icon: Database },
];

export function Sidebar({
  weights, filters, villages, lulcNames,
  onWeightChange, onFilterChange, activeSection, onSectionChange,
}: SidebarProps) {
  const [weightsOpen, setWeightsOpen] = useState(true);
  const [filtersOpen,  setFiltersOpen]  = useState(false);

  const total = Object.values(weights).reduce((a, b) => a + b, 0) || 1;
  const norm  = Object.fromEntries(
    Object.entries(weights).map(([k, v]) => [k, v / total])
  ) as Record<keyof Weights, number>;

  return (
    <aside className="sidebar">
      {/* ── Navigation ──────────────────────────────────────────────── */}
      <nav style={{ padding: "12px 0 4px" }}>
        <div className="sidebar-section-label" style={{ paddingTop: 8 }}>Navigation</div>
        {NAV.map(({ id, label, Icon }) => (
          <button
            key={id}
            className={`nav-item${activeSection === id ? " active" : ""}`}
            onClick={() => onSectionChange(id)}
            data-testid={`nav-${id}`}
          >
            <span className="nav-icon">
              <Icon size={16} strokeWidth={activeSection === id ? 2.5 : 2} />
            </span>
            {label}
          </button>
        ))}
      </nav>

      <div className="divider" style={{ margin: "8px 16px" }} />

      {/* ── Weights ─────────────────────────────────────────────────── */}
      <div style={{ flex: 1, overflowY: "auto", overscrollBehavior: "contain" }}>
        <button
          style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            width: "100%", background: "none", border: "none", cursor: "pointer",
            padding: "8px 20px 4px", gap: 6,
          }}
          onClick={() => setWeightsOpen(!weightsOpen)}
        >
          <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <SlidersHorizontal size={13} color="hsl(var(--foreground-tertiary))" />
            <span className="sidebar-section-label" style={{ padding: 0 }}>Factor Weights</span>
          </span>
          {weightsOpen
            ? <ChevronUp size={13} color="hsl(var(--foreground-tertiary))" />
            : <ChevronDown size={13} color="hsl(var(--foreground-tertiary))" />}
        </button>

        {weightsOpen && (
          <div style={{ padding: "4px 20px 8px" }}>
            {/* Weight distribution bar */}
            <div className="weight-bar-track" style={{ marginBottom: 16 }}>
              {FACTOR_CONFIG.map(({ key, color }) => (
                <div
                  key={key}
                  style={{
                    width: `${norm[key] * 100}%`,
                    background: color,
                    transition: "width 0.3s ease",
                    minWidth: norm[key] > 0 ? 2 : 0,
                  }}
                />
              ))}
            </div>

            {FACTOR_CONFIG.map(({ key, label, icon, color }) => (
              <ControlledSlider
                key={key}
                factorKey={key}
                label={label}
                icon={icon}
                color={color}
                value={weights[key]}
                normalised={norm[key]}
                onChange={onWeightChange}
              />
            ))}

            {/* Legend dots */}
            <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 10px", marginTop: 4 }}>
              {FACTOR_CONFIG.map(({ key, label, color }) => (
                <span key={key} style={{
                  display: "flex", alignItems: "center", gap: 4,
                  fontSize: 10, color: "hsl(var(--foreground-tertiary))",
                }}>
                  <span style={{
                    width: 7, height: 7, borderRadius: 2,
                    background: color, display: "inline-block", flexShrink: 0,
                  }} />
                  {label.split(" ")[0]}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="divider" style={{ margin: "4px 16px" }} />

        {/* ── Filters ───────────────────────────────────────────────── */}
        <button
          style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            width: "100%", background: "none", border: "none", cursor: "pointer",
            padding: "8px 20px 4px", gap: 6,
          }}
          onClick={() => setFiltersOpen(!filtersOpen)}
        >
          <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <Filter size={13} color="hsl(var(--foreground-tertiary))" />
            <span className="sidebar-section-label" style={{ padding: 0 }}>Filters</span>
          </span>
          {filtersOpen
            ? <ChevronUp size={13} color="hsl(var(--foreground-tertiary))" />
            : <ChevronDown size={13} color="hsl(var(--foreground-tertiary))" />}
        </button>

        {filtersOpen && (
          <div style={{ padding: "4px 20px 12px", display: "flex", flexDirection: "column", gap: 12 }}>
            {/* Village */}
            <div>
              <label style={{ fontSize: 11, fontWeight: 500, color: "hsl(var(--foreground-tertiary))", display: "block", marginBottom: 4 }}>
                Village / Zone
              </label>
              <select
                className="filter-select"
                style={{ width: "100%" }}
                value={filters.village}
                onChange={(e) => onFilterChange("village", e.target.value)}
                data-testid="filter-village"
              >
                <option value="all">All Villages</option>
                {villages.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            </div>

            {/* LULC */}
            <div>
              <label style={{ fontSize: 11, fontWeight: 500, color: "hsl(var(--foreground-tertiary))", display: "block", marginBottom: 4 }}>
                Land Cover Class
              </label>
              <select
                className="filter-select"
                style={{ width: "100%" }}
                value={filters.lulc_name}
                onChange={(e) => onFilterChange("lulc_name", e.target.value)}
                data-testid="filter-lulc"
              >
                <option value="all">All Classes</option>
                {lulcNames.map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>

            {/* Slope */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
                <label style={{ fontSize: 11, fontWeight: 500, color: "hsl(var(--foreground-tertiary))" }}>Max Slope</label>
                <span style={{ fontSize: 11, fontWeight: 600, color: "hsl(var(--primary))", fontFamily: "monospace" }}>
                  {filters.max_slope}°
                </span>
              </div>
              <input type="range" min={1} max={30} step={0.5}
                value={filters.max_slope}
                onChange={(e) => onFilterChange("max_slope", Number(e.target.value))}
                className="weight-slider"
                style={{ accentColor: "hsl(217 91% 60%)" }}
                data-testid="filter-slope" />
            </div>

            {/* Grid distance */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
                <label style={{ fontSize: 11, fontWeight: 500, color: "hsl(var(--foreground-tertiary))" }}>Max Grid Dist.</label>
                <span style={{ fontSize: 11, fontWeight: 600, color: "hsl(var(--primary))", fontFamily: "monospace" }}>
                  {filters.max_power_dist} km
                </span>
              </div>
              <input type="range" min={1} max={30} step={1}
                value={filters.max_power_dist}
                onChange={(e) => onFilterChange("max_power_dist", Number(e.target.value))}
                className="weight-slider"
                style={{ accentColor: "hsl(217 91% 60%)" }}
                data-testid="filter-power-dist" />
            </div>
          </div>
        )}
      </div>

      {/* ── Footer ────────────────────────────────────────────────────── */}
      <div style={{
        padding: "10px 20px 12px",
        borderTop: "1px solid hsl(var(--border))",
        display: "flex", flexDirection: "column", gap: 2,
      }}>
        <div style={{ fontSize: 10, color: "hsl(var(--foreground-tertiary))", fontWeight: 500 }}>
          Auroville Consulting
        </div>
        <div style={{ fontSize: 10, color: "hsl(var(--foreground-tertiary))", opacity: 0.7 }}>
          ESA · NASA · PVGIS · OpenStreetMap
        </div>
      </div>
    </aside>
  );
}
