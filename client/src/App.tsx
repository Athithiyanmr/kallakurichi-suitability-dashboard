import React, { useState, useCallback } from "react";
import { Switch, Route, Router } from "wouter";
import { useHashLocation } from "wouter/use-hash-location";
import { QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/toaster";
import { queryClient } from "./lib/queryClient";
import { useParcels, useMeta } from "./hooks/useParcels";
import { Sidebar } from "./components/Sidebar";
import { KPIRow } from "./components/KPIRow";
import { SuitabilityMap } from "./components/SuitabilityMap";
import {
  SuitabilityDoughnut, FactorBars, GHIScatter, LULCAreaBars,
  AreaByClassBars, SlopeScoreScatter,
} from "./components/Charts";
import { ParcelTable } from "./components/ParcelTable";
import DataSources from "./components/DataSources";
import type { Weights, Filters } from "./types";
import { Map, BarChart3, Table2, Database, RefreshCw } from "lucide-react";

// ─── Default state ────────────────────────────────────────────────────────────
const DEFAULT_WEIGHTS: Weights = {
  slope: 5, lulc: 5, ghi: 5, power: 5, road: 5, temp: 5,
};
const DEFAULT_FILTERS: Filters = {
  lulc:           "all",
  suit_class:     "all",
  max_slope:      20,
  max_power_dist: 30,
  min_area:       0.5,
};

type Section = "map" | "charts" | "table" | "data";

const NAV: Array<{ id: Section; label: string; Icon: typeof Map }> = [
  { id: "map",    label: "Suitability Map",  Icon: Map },
  { id: "charts", label: "Factor Analysis",  Icon: BarChart3 },
  { id: "table",  label: "Parcel Rankings",  Icon: Table2 },
  { id: "data",   label: "Data Sources",     Icon: Database },
];

// ─── SVG Logo ─────────────────────────────────────────────────────────────────
function Logo() {
  return (
    <svg viewBox="0 0 32 32" width="30" height="30" fill="none" aria-label="Solar Suitability">
      <rect width="32" height="32" rx="8" fill="hsl(217 91% 60%)" />
      <circle cx="16" cy="16" r="5" fill="white" />
      <line x1="16" y1="5"  x2="16" y2="8"  stroke="white" strokeWidth="2" strokeLinecap="round"/>
      <line x1="16" y1="24" x2="16" y2="27" stroke="white" strokeWidth="2" strokeLinecap="round"/>
      <line x1="5"  y1="16" x2="8"  y2="16" stroke="white" strokeWidth="2" strokeLinecap="round"/>
      <line x1="24" y1="16" x2="27" y2="16" stroke="white" strokeWidth="2" strokeLinecap="round"/>
      <line x1="8.5"  y1="8.5"  x2="10.6" y2="10.6" stroke="white" strokeWidth="1.8" strokeLinecap="round"/>
      <line x1="21.4" y1="21.4" x2="23.5" y2="23.5" stroke="white" strokeWidth="1.8" strokeLinecap="round"/>
      <line x1="23.5" y1="8.5"  x2="21.4" y2="10.6" stroke="white" strokeWidth="1.8" strokeLinecap="round"/>
      <line x1="10.6" y1="21.4" x2="8.5"  y2="23.5" stroke="white" strokeWidth="1.8" strokeLinecap="round"/>
    </svg>
  );
}

// ─── Charts 3×2 grid ─────────────────────────────────────────────────────────
function ChartsSection({ parcels }: { parcels: any[] }) {
  const n   = parcels.length;
  const avg = n ? (parcels.reduce((s: number, p: any) => s + p.score, 0) / n).toFixed(2) : "—";
  const totalHa = n ? parcels.reduce((s: number, p: any) => s + p.area_ha, 0) : 0;
  return (
    <div className="scrollable section-body" style={{ padding: "20px 24px 32px" }}>
      <div style={{ marginBottom: 20 }}>
        <div className="section-title">Factor Analysis</div>
        <div className="section-subtitle">
          {n.toLocaleString()} polygons · {(totalHa / 1000).toFixed(1)}k ha total · Avg score {avg}/4.0
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div className="chart-card fade-up">
          <div className="chart-title">Suitability Distribution</div>
          <div className="chart-subtitle">Polygon count by classification tier</div>
          <SuitabilityDoughnut parcels={parcels} />
        </div>
        <div className="chart-card fade-up" style={{ animationDelay: "0.05s" }}>
          <div className="chart-title">Area by Suitability Class</div>
          <div className="chart-subtitle">Total hectares per tier</div>
          <AreaByClassBars parcels={parcels} />
        </div>
        <div className="chart-card fade-up" style={{ animationDelay: "0.10s" }}>
          <div className="chart-title">Average Factor Scores</div>
          <div className="chart-subtitle">Mean score per suitability factor (1–4)</div>
          <FactorBars parcels={parcels} />
        </div>
        <div className="chart-card fade-up" style={{ animationDelay: "0.15s" }}>
          <div className="chart-title">Land Cover Area Split</div>
          <div className="chart-subtitle">Bare / sparse veg vs Shrubland</div>
          <LULCAreaBars parcels={parcels} />
        </div>
        <div className="chart-card fade-up" style={{ animationDelay: "0.20s" }}>
          <div className="chart-title">GHI vs Suitability</div>
          <div className="chart-subtitle">Solar irradiation correlation</div>
          <GHIScatter parcels={parcels} />
        </div>
        <div className="chart-card fade-up" style={{ animationDelay: "0.25s" }}>
          <div className="chart-title">Slope vs Suitability</div>
          <div className="chart-subtitle">Terrain gradient correlation</div>
          <SlopeScoreScatter parcels={parcels} />
        </div>
      </div>
    </div>
  );
}

// ─── Table section ────────────────────────────────────────────────────────────
function TableSection({
  parcels, filters, lulcTypes, suitClasses, onFilterChange,
}: {
  parcels: any[];
  filters: Filters;
  lulcTypes: string[];
  suitClasses: string[];
  onFilterChange: (k: keyof Filters, v: string | number) => void;
}) {
  return (
    <div className="section-body" style={{ overflow: "hidden", display: "flex", flexDirection: "column" }}>
      {/* Inline filter bar */}
      <div className="filter-row">
        <span className="filter-label">Filter:</span>
        {/* LULC filter */}
        <select
          className="filter-select"
          value={filters.lulc}
          onChange={(e) => onFilterChange("lulc", e.target.value)}
        >
          <option value="all">All Land Cover</option>
          {lulcTypes.map((l) => <option key={l} value={l}>{l}</option>)}
        </select>
        {/* Suitability class filter */}
        <select
          className="filter-select"
          value={filters.suit_class}
          onChange={(e) => onFilterChange("suit_class", e.target.value)}
        >
          <option value="all">All Classes</option>
          {suitClasses.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>

        <div className="filter-label" style={{ marginLeft: 8 }}>Max Slope:</div>
        <span className="font-mono" style={{ fontSize: 12, color: "hsl(var(--primary))", minWidth: 28 }}>
          {filters.max_slope}°
        </span>
        <input
          type="range" min={1} max={30} step={0.5}
          value={filters.max_slope}
          className="weight-slider"
          style={{ width: 90, accentColor: "hsl(217 91% 60%)" }}
          onChange={(e) => onFilterChange("max_slope", Number(e.target.value))}
        />

        <div className="filter-label" style={{ marginLeft: 8 }}>Min Area:</div>
        <span className="font-mono" style={{ fontSize: 12, color: "hsl(var(--primary))", minWidth: 38 }}>
          {filters.min_area} ha
        </span>
        <input
          type="range" min={0.5} max={50} step={0.5}
          value={filters.min_area}
          className="weight-slider"
          style={{ width: 80, accentColor: "hsl(217 91% 60%)" }}
          onChange={(e) => onFilterChange("min_area", Number(e.target.value))}
        />

        <div style={{ marginLeft: "auto" }}>
          <span className="chip blue">{parcels.length.toLocaleString()} parcels</span>
        </div>
      </div>
      <ParcelTable parcels={parcels} />
    </div>
  );
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────
function Dashboard() {
  const [section,  setSection]  = useState<Section>("map");
  const [weights,  setWeights]  = useState<Weights>(DEFAULT_WEIGHTS);
  const [filters,  setFilters]  = useState<Filters>(DEFAULT_FILTERS);

  const { data: parcels = [], isLoading } = useParcels(weights, filters);
  const { data: meta } = useMeta();

  const onWeightChange = useCallback((key: keyof Weights, val: number) => {
    setWeights((prev) => ({ ...prev, [key]: val }));
  }, []);
  const onFilterChange = useCallback((key: keyof Filters, val: string | number) => {
    setFilters((prev) => ({ ...prev, [key]: val }));
  }, []);

  const nHigh    = parcels.filter((p) => p.score >= 2.75).length;
  const totalHa  = parcels.reduce((s, p) => s + p.area_ha, 0);

  return (
    <div className="app-root">

      {/* ── Top Bar ──────────────────────────────────────────────────── */}
      <header className="top-bar">
        <div className="brand-area">
          <div className="brand-logo"><Logo /></div>
          <div>
            <div className="brand-title">Solar Suitability</div>
            <div className="brand-sub">Kallakurichi District · Barren Land Analysis</div>
          </div>
        </div>

        <div className="top-bar-right">
          {isLoading ? (
            <span className="chip" style={{ gap: 5 }}>
              <RefreshCw size={10} className="animate-spin" /> Computing…
            </span>
          ) : (
            <span className="chip green">● Live</span>
          )}
          <span className="chip blue">{parcels.length.toLocaleString()} polygons</span>
          <span className="chip">{nHigh.toLocaleString()} high suitability</span>
          <span className="chip">
            {totalHa >= 1000 ? `${(totalHa / 1000).toFixed(1)}k ha` : `${totalHa.toFixed(0)} ha`}
          </span>
          <span className="chip" style={{ display: "flex", gap: 4 }}>
            <span style={{ opacity: 0.7 }}>Tamil Nadu</span>
            <span>·</span>
            <span>ESA · NASA · PVGIS · OSM</span>
          </span>
        </div>
      </header>

      {/* ── Content Row ──────────────────────────────────────────────── */}
      <div className="content-row">

        <Sidebar
          weights={weights}
          filters={filters}
          lulcTypes={meta?.lulc_types ?? ["Bare/sparse veg", "Shrubland"]}
          suitClasses={meta?.suit_classes ?? ["Very High", "High", "Moderate", "Low"]}
          onWeightChange={onWeightChange}
          onFilterChange={onFilterChange}
          activeSection={section}
          onSectionChange={(s) => setSection(s as Section)}
        />

        <div className="main-content">

          {/* Tab bar */}
          <div className="tab-bar">
            {NAV.map(({ id, label, Icon }) => (
              <button
                key={id}
                className={`tab-btn${section === id ? " active" : ""}`}
                onClick={() => setSection(id)}
                data-testid={`tab-${id}`}
              >
                <Icon size={13} strokeWidth={2} />
                {label}
                {id === "table" && (
                  <span className="tab-count">{parcels.length}</span>
                )}
              </button>
            ))}
          </div>

          {/* KPI row */}
          <KPIRow parcels={parcels} />

          {/* Sections */}
          {section === "map" && (
            <div className="section-body" style={{ overflow: "hidden", display: "flex", flexDirection: "column" }}>
              <SuitabilityMap parcels={parcels} weights={weights} filters={filters} />
            </div>
          )}
          {section === "charts" && (
            <div className="section-body scrollable" style={{ overflowY: "auto" }}>
              <ChartsSection parcels={parcels} />
            </div>
          )}
          {section === "table" && (
            <TableSection
              parcels={parcels}
              filters={filters}
              lulcTypes={meta?.lulc_types ?? ["Bare/sparse veg", "Shrubland"]}
              suitClasses={meta?.suit_classes ?? ["Very High", "High", "Moderate", "Low"]}
              onFilterChange={onFilterChange}
            />
          )}
          {section === "data" && (
            <div className="section-body" style={{ overflowY: "auto", padding: "20px 24px 32px" }}>
              <DataSources />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Root ─────────────────────────────────────────────────────────────────────
export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Router hook={useHashLocation}>
          <Switch>
            <Route path="/" component={Dashboard} />
            <Route component={Dashboard} />
          </Switch>
        </Router>
      </TooltipProvider>
    </QueryClientProvider>
  );
}
