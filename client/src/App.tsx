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
import { Map, BarChart3, Table2, Database, RefreshCw } from "lucide-react";

// ─── Default state ─────────────────────────────────────────────────────────────
const DEFAULT_WEIGHTS: Weights = {
  slope: 5,
  lulc:  5,
  ghi:   5,
  power: 5,
  road:  5,
  temp:  5,
};

const DEFAULT_FILTERS: Filters = {
  village:        "all",
  lulc_name:      "all",
  max_slope:      20,
  max_power_dist: 15,
};

type Section = "map" | "charts" | "table" | "data";

const NAV_ITEMS: Array<{ id: Section; label: string; Icon: typeof Map }> = [
  { id: "map",    label: "Suitability Map",  Icon: Map },
  { id: "charts", label: "Analysis Charts",  Icon: BarChart3 },
  { id: "table",  label: "Parcel Table",     Icon: Table2 },
  { id: "data",   label: "Data Sources",     Icon: Database },
];

// ─── Chart Card wrapper ───────────────────────────────────────────────────────
function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        background:   "hsl(var(--card))",
        border:       "1px solid hsl(var(--border))",
        borderRadius: "10px",
        padding:      "20px",
      }}
    >
      <h3 style={{ fontSize: "13px", fontWeight: 700, color: "hsl(var(--foreground))", marginBottom: "16px" }}>
        {title}
      </h3>
      {children}
    </div>
  );
}

// ─── Charts layout (2×2 grid) ──────────────────────────────────────────────────
function ChartsSection({ parcels }: { parcels: any[] }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
      <ChartCard title="Suitability Distribution">
        <SuitabilityDoughnut parcels={parcels} />
      </ChartCard>
      <ChartCard title="Average Factor Scores">
        <FactorBars parcels={parcels} />
      </ChartCard>
      <ChartCard title="Top Villages by Score">
        <VillageBars parcels={parcels} />
      </ChartCard>
      <ChartCard title="GHI vs Suitability Score">
        <GHIScatter parcels={parcels} />
      </ChartCard>
    </div>
  );
}

// ─── Main Dashboard page ────────────────────────────────────────────────────────
function Dashboard() {
  const [section, setSection]   = useState<Section>("map");
  const [mapMode]               = useState<"circles" | "heat">("circles");
  const [weights, setWeights]   = useState<Weights>(DEFAULT_WEIGHTS);
  const [filters, setFilters]   = useState<Filters>(DEFAULT_FILTERS);

  const { data: parcels = [], isLoading } = useParcels(weights, filters);
  const { data: meta }                    = useMeta();

  const handleWeightChange = useCallback((key: keyof Weights, val: number) => {
    setWeights(prev => ({ ...prev, [key]: val }));
  }, []);

  const handleFilterChange = useCallback((key: keyof Filters, val: string | number) => {
    setFilters(prev => ({ ...prev, [key]: val }));
  }, []);

  return (
    <div
      style={{
        display:             "grid",
        gridTemplateColumns: "260px 1fr",
        gridTemplateRows:    "56px 1fr",
        height:              "100dvh",
        overflow:            "hidden",
        background:          "hsl(var(--background))",
      }}
    >
      {/* ── Sidebar ────────────────────────────────────────────────────────── */}
      <div style={{ gridRow: "1 / -1", overflow: "hidden" }}>
        <Sidebar
          weights={weights}
          filters={filters}
          villages={meta?.villages ?? []}
          lulcNames={meta?.lulc_names ?? []}
          onWeightChange={handleWeightChange}
          onFilterChange={handleFilterChange}
          activeSection={section}
          onSectionChange={(s) => setSection(s as Section)}
        />
      </div>

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header
        style={{
          gridColumn:    "2",
          display:       "flex",
          alignItems:    "center",
          justifyContent:"space-between",
          padding:       "0 24px",
          gap:           "16px",
          borderBottom:  "1px solid hsl(var(--border))",
          background:    "hsl(var(--card))",
          position:      "sticky",
          top:           0,
          zIndex:        20,
        }}
      >
        {/* Breadcrumb */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {NAV_ITEMS.filter(n => n.id === section).map(({ label, Icon }) => (
            <span key={label} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <Icon size={15} style={{ color: "hsl(var(--primary))" }} />
              <span style={{ fontSize: "13px", fontWeight: 600, color: "hsl(var(--foreground))", letterSpacing: "-0.01em" }}>
                {label}
              </span>
            </span>
          ))}
          {isLoading && (
            <span style={{ marginLeft: "6px", fontSize: "11px", color: "hsl(var(--muted-foreground))", display: "flex", alignItems: "center", gap: "4px" }}>
              <RefreshCw size={10} className="animate-spin" /> Computing…
            </span>
          )}
        </div>

        {/* Section tabs */}
        <nav style={{ display: "flex", gap: "2px" }}>
          {NAV_ITEMS.map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => setSection(id)}
              data-testid={`nav-${id}`}
              style={{
                display:       "flex",
                alignItems:    "center",
                gap:           "5px",
                padding:       "5px 12px",
                borderRadius:  "6px",
                fontSize:      "12px",
                fontWeight:    500,
                border:        "none",
                cursor:        "pointer",
                transition:    "all 0.15s",
                background:    section === id ? "hsl(var(--primary))" : "transparent",
                color:         section === id ? "hsl(var(--primary-foreground))" : "hsl(var(--muted-foreground))",
              }}
            >
              <Icon size={12} />
              {label}
            </button>
          ))}
        </nav>
      </header>

      {/* ── Main ───────────────────────────────────────────────────────────── */}
      <main
        style={{
          gridColumn:        "2",
          overflowY:         section === "map" ? "hidden" : "auto",
          overscrollBehavior:"contain",
          display:           "flex",
          flexDirection:     "column",
        }}
      >
        {/* KPI Row */}
        <div style={{ flexShrink: 0, padding: "14px 24px 0" }}>
          <KPIRow parcels={parcels} />
        </div>

        {/* Section body */}
        <div
          style={{
            flex:          1,
            padding:       section === "map" ? "12px 24px 16px" : "16px 24px 24px",
            overflow:      section === "map" ? "hidden" : "visible",
            display:       "flex",
            flexDirection: "column",
          }}
        >
          {section === "map" && (
            <SuitabilityMap parcels={parcels} mapMode={mapMode} />
          )}
          {section === "charts" && (
            <ChartsSection parcels={parcels} />
          )}
          {section === "table" && (
            <ParcelTable parcels={parcels} />
          )}
          {section === "data" && (
            <DataSources />
          )}
        </div>
      </main>
    </div>
  );
}

// ─── Root ──────────────────────────────────────────────────────────────────────
function App() {
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

export default App;
