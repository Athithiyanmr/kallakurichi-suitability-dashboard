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
import { SuitabilityDoughnut, FactorBars, VillageBars, GHIScatter } from "./components/Charts";
import { ParcelTable } from "./components/ParcelTable";
import DataSources from "./components/DataSources";
import type { Weights, Filters } from "./types";
import { Map, BarChart3, Table2, Database, RefreshCw, Layers } from "lucide-react";

// ─── Default state ─────────────────────────────────────────────────────────────
const DEFAULT_WEIGHTS: Weights = {
  slope: 5, lulc: 5, ghi: 5, power: 5, road: 5, temp: 5,
};
const DEFAULT_FILTERS: Filters = {
  village: "all", lulc_name: "all", max_slope: 20, max_power_dist: 15,
};

type Section = "map" | "charts" | "table" | "data";

const NAV: Array<{ id: Section; label: string; Icon: typeof Map }> = [
  { id: "map",    label: "Suitability Map",  Icon: Map },
  { id: "charts", label: "Factor Analysis",  Icon: BarChart3 },
  { id: "table",  label: "Parcel Rankings",  Icon: Table2 },
  { id: "data",   label: "Data Sources",     Icon: Database },
];

// ─── Google-style SVG logo ─────────────────────────────────────────────────────
function Logo() {
  return (
    <svg viewBox="0 0 32 32" width="30" height="30" fill="none" aria-label="Solar Suitability">
      <rect width="32" height="32" rx="8" fill="hsl(217 91% 60%)" />
      {/* Sun rays */}
      <circle cx="16" cy="16" r="5" fill="white" />
      <line x1="16" y1="5" x2="16" y2="8" stroke="white" strokeWidth="2" strokeLinecap="round"/>
      <line x1="16" y1="24" x2="16" y2="27" stroke="white" strokeWidth="2" strokeLinecap="round"/>
      <line x1="5" y1="16" x2="8" y2="16" stroke="white" strokeWidth="2" strokeLinecap="round"/>
      <line x1="24" y1="16" x2="27" y2="16" stroke="white" strokeWidth="2" strokeLinecap="round"/>
      <line x1="8.5" y1="8.5" x2="10.6" y2="10.6" stroke="white" strokeWidth="1.8" strokeLinecap="round"/>
      <line x1="21.4" y1="21.4" x2="23.5" y2="23.5" stroke="white" strokeWidth="1.8" strokeLinecap="round"/>
      <line x1="23.5" y1="8.5" x2="21.4" y2="10.6" stroke="white" strokeWidth="1.8" strokeLinecap="round"/>
      <line x1="10.6" y1="21.4" x2="8.5" y2="23.5" stroke="white" strokeWidth="1.8" strokeLinecap="round"/>
    </svg>
  );
}

// ─── Charts 2×2 grid ──────────────────────────────────────────────────────────
function ChartsSection({ parcels }: { parcels: any[] }) {
  const n = parcels.length;
  const avg = n ? (parcels.reduce((s, p) => s + p.suitability_score, 0) / n).toFixed(2) : "—";
  return (
    <div className="scrollable section-body" style={{ padding: "20px 24px 32px" }}>
      {/* Section header */}
      <div style={{ marginBottom: 20 }}>
        <div className="section-title">Factor Analysis</div>
        <div className="section-subtitle">
          {n.toLocaleString()} parcels · Avg suitability score {avg}/4.0
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div className="chart-card fade-up">
          <div className="chart-title">Suitability Distribution</div>
          <div className="chart-subtitle">Count by classification tier</div>
          <SuitabilityDoughnut parcels={parcels} />
        </div>
        <div className="chart-card fade-up" style={{ animationDelay: "0.05s" }}>
          <div className="chart-title">Average Factor Scores</div>
          <div className="chart-subtitle">Mean score per suitability factor (1–4)</div>
          <FactorBars parcels={parcels} />
        </div>
        <div className="chart-card fade-up" style={{ animationDelay: "0.10s" }}>
          <div className="chart-title">Village Performance</div>
          <div className="chart-subtitle">Average suitability score by zone</div>
          <VillageBars parcels={parcels} />
        </div>
        <div className="chart-card fade-up" style={{ animationDelay: "0.15s" }}>
          <div className="chart-title">GHI vs Suitability</div>
          <div className="chart-subtitle">Solar irradiation correlation</div>
          <GHIScatter parcels={parcels} />
        </div>
      </div>
    </div>
  );
}

// ─── Table section with filter row ────────────────────────────────────────────
function TableSection({
  parcels, filters, villages, lulcNames, onFilterChange,
}: {
  parcels: any[]; filters: Filters; villages: string[]; lulcNames: string[];
  onFilterChange: (k: keyof Filters, v: string | number) => void;
}) {
  return (
    <div className="section-body" style={{ overflow: "hidden", display: "flex", flexDirection: "column" }}>
      {/* Inline filter bar above table */}
      <div className="filter-row">
        <span className="filter-label">Filter:</span>
        <select
          className="filter-select"
          value={filters.village}
          onChange={(e) => onFilterChange("village", e.target.value)}
        >
          <option value="all">All Villages</option>
          {villages.map((v) => <option key={v} value={v}>{v}</option>)}
        </select>
        <select
          className="filter-select"
          value={filters.lulc_name}
          onChange={(e) => onFilterChange("lulc_name", e.target.value)}
        >
          <option value="all">All Land Cover</option>
          {lulcNames.map((l) => <option key={l} value={l}>{l}</option>)}
        </select>

        <div className="filter-label" style={{ marginLeft: 8 }}>
          Max Slope:
        </div>
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

        <div className="filter-label" style={{ marginLeft: 8 }}>
          Max Grid Dist:
        </div>
        <span className="font-mono" style={{ fontSize: 12, color: "hsl(var(--primary))", minWidth: 36 }}>
          {filters.max_power_dist} km
        </span>
        <input
          type="range" min={1} max={30} step={1}
          value={filters.max_power_dist}
          className="weight-slider"
          style={{ width: 90, accentColor: "hsl(217 91% 60%)" }}
          onChange={(e) => onFilterChange("max_power_dist", Number(e.target.value))}
        />

        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6 }}>
          <span className="chip">
            {parcels.length.toLocaleString()} parcels
          </span>
        </div>
      </div>
      <ParcelTable parcels={parcels} />
    </div>
  );
}

// ─── Main Dashboard ────────────────────────────────────────────────────────────
function Dashboard() {
  const [section, setSection] = useState<Section>("map");
  const [weights, setWeights] = useState<Weights>(DEFAULT_WEIGHTS);
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);

  const { data: parcels = [], isLoading } = useParcels(weights, filters);
  const { data: meta } = useMeta();

  const onWeightChange = useCallback((key: keyof Weights, val: number) => {
    setWeights((prev) => ({ ...prev, [key]: val }));
  }, []);
  const onFilterChange = useCallback((key: keyof Filters, val: string | number) => {
    setFilters((prev) => ({ ...prev, [key]: val }));
  }, []);

  const highCount = parcels.filter((p) => p.suitability_score >= 2.5).length;

  return (
    <div className="app-root">

      {/* ── Top Bar ──────────────────────────────────────────────────────── */}
      <header className="top-bar">
        {/* Brand */}
        <div className="brand-area">
          <div className="brand-logo">
            <Logo />
          </div>
          <div>
            <div className="brand-title">Solar Suitability</div>
            <div className="brand-sub">Kallakurichi District</div>
          </div>
        </div>

        {/* Spacer + status chips */}
        <div className="top-bar-right">
          {isLoading ? (
            <span className="chip" style={{ gap: 5 }}>
              <RefreshCw size={10} className="animate-spin" />
              Computing…
            </span>
          ) : (
            <span className="chip green">
              ● Live
            </span>
          )}
          <span className="chip blue">
            {parcels.length.toLocaleString()} parcels
          </span>
          <span className="chip">
            {highCount} high suitability
          </span>
          <span className="chip" style={{ display: "flex", gap: 4 }}>
            <span style={{ opacity: 0.7 }}>Tamil Nadu</span>
            <span>·</span>
            <span>ESA · NASA · PVGIS · OSM</span>
          </span>
        </div>
      </header>

      {/* ── Content Row ──────────────────────────────────────────────────── */}
      <div className="content-row">

        {/* Sidebar */}
        <Sidebar
          weights={weights}
          filters={filters}
          villages={meta?.villages ?? []}
          lulcNames={meta?.lulc_names ?? []}
          onWeightChange={onWeightChange}
          onFilterChange={onFilterChange}
          activeSection={section}
          onSectionChange={(s) => setSection(s as Section)}
        />

        {/* Right pane */}
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

          {/* Section */}
          {section === "map" && (
            <div className="section-body" style={{ overflow: "hidden", display: "flex", flexDirection: "column" }}>
              <SuitabilityMap parcels={parcels} mapMode="circles" />
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
              villages={meta?.villages ?? []}
              lulcNames={meta?.lulc_names ?? []}
              onFilterChange={onFilterChange}
            />
          )}
          {section === "data" && (
            <div
              className="section-body"
              style={{ overflowY: "auto", padding: "20px 24px 32px" }}
            >
              <DataSources />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Root ──────────────────────────────────────────────────────────────────────
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
