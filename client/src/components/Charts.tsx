import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, ArcElement,
  Tooltip, Legend, PointElement, LineElement, Filler,
} from "chart.js";
import { Bar, Doughnut, Scatter } from "react-chartjs-2";
import type { Parcel } from "../types";

ChartJS.register(
  CategoryScale, LinearScale, BarElement, ArcElement,
  Tooltip, Legend, PointElement, LineElement, Filler,
);

// ─── Palette ──────────────────────────────────────────────────────────────────
const VH_COLOR   = "#0d8043";
const H_COLOR    = "#1a73e8";
const MOD_COLOR  = "#e37400";
const LOW_COLOR  = "#c5221f";
const G_PURPLE   = "#a142f4";
const G_SLATE    = "#5f6368";

const SCORE_COLORS   = [VH_COLOR, H_COLOR, MOD_COLOR, LOW_COLOR];
const FACTOR_COLORS  = [G_SLATE, VH_COLOR, "#fbbc04", H_COLOR, G_PURPLE, LOW_COLOR];

const CHART_FONT = { family: "'Inter', system-ui, sans-serif", size: 11 };
const GRID_COLOR = "rgba(0,0,0,0.05)";

const TOOLTIP_STYLE = {
  backgroundColor: "rgba(32,33,36,0.92)",
  titleColor: "#fff",
  bodyColor: "#bdc1c6",
  borderColor: "transparent",
  cornerRadius: 8,
  padding: 10,
  titleFont: { ...CHART_FONT, weight: "600" as const },
  bodyFont: { ...CHART_FONT },
  displayColors: true,
  boxWidth: 10,
  boxHeight: 10,
  boxPadding: 4,
};

// ─── Suitability Doughnut ─────────────────────────────────────────────────────
export function SuitabilityDoughnut({ parcels }: { parcels: Parcel[] }) {
  const bins = { "Very High": 0, "High": 0, "Moderate": 0, "Low": 0 };
  for (const p of parcels) {
    if      (p.score >= 3.5)  bins["Very High"]++;
    else if (p.score >= 2.75) bins["High"]++;
    else if (p.score >= 2.0)  bins["Moderate"]++;
    else                       bins["Low"]++;
  }
  const n = parcels.length || 1;
  return (
    <Doughnut
      data={{
        labels: Object.keys(bins),
        datasets: [{
          data: Object.values(bins),
          backgroundColor: SCORE_COLORS,
          borderColor: "#fff",
          borderWidth: 3,
          hoverOffset: 8,
          hoverBorderWidth: 3,
        }],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: true,
        cutout: "65%",
        plugins: {
          legend: {
            position: "bottom",
            labels: {
              font: CHART_FONT,
              boxWidth: 10, boxHeight: 10,
              padding: 12,
              usePointStyle: true,
              pointStyleWidth: 10,
            },
          },
          tooltip: {
            ...TOOLTIP_STYLE,
            callbacks: {
              label: (ctx) =>
                `  ${ctx.label}: ${ctx.parsed.toLocaleString()} (${Math.round(ctx.parsed / n * 100)}%)`,
            },
          },
        },
      }}
    />
  );
}

// ─── Area-by-class Bar (replaces VillageBars — no village in new schema) ──────
export function AreaByClassBars({ parcels }: { parcels: Parcel[] }) {
  const map: Record<string, number> = {};
  for (const p of parcels) {
    map[p.class] = (map[p.class] ?? 0) + p.area_ha;
  }
  const ORDER = ["Very High", "High", "Moderate", "Low"];
  const labels = ORDER.filter((k) => map[k] !== undefined);
  const data   = labels.map((k) => map[k]);
  const colors = labels.map((k) =>
    k === "Very High" ? VH_COLOR : k === "High" ? H_COLOR : k === "Moderate" ? MOD_COLOR : LOW_COLOR
  );

  return (
    <Bar
      data={{
        labels,
        datasets: [{
          label: "Area (ha)",
          data,
          backgroundColor: colors.map((c) => `${c}BB`),
          borderColor: colors,
          borderWidth: 2,
          borderRadius: 6,
          borderSkipped: false,
          barThickness: 36,
        }],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            ...TOOLTIP_STYLE,
            callbacks: {
              label: (ctx) =>
                `  Area: ${(ctx.parsed.y as number).toLocaleString()} ha`,
            },
          },
        },
        scales: {
          y: {
            grid: { color: GRID_COLOR },
            ticks: { font: CHART_FONT, color: "#80868b" },
            border: { dash: [3, 3] },
            title: {
              display: true, text: "Area (ha)",
              font: { ...CHART_FONT, size: 10 }, color: "#80868b",
            },
          },
          x: {
            grid: { display: false },
            ticks: { font: CHART_FONT, color: "#5f6368", maxRotation: 0 },
          },
        },
      }}
    />
  );
}

// ─── Factor Bars ──────────────────────────────────────────────────────────────
export function FactorBars({ parcels }: { parcels: Parcel[] }) {
  const n = parcels.length || 1;
  const labels = ["Slope", "Land Cover", "Solar GHI", "Grid Access", "Road Access", "Temperature"];
  type ScoreKey = "s_slope" | "s_lulc" | "s_ghi" | "s_power" | "s_road" | "s_temp";
  const keys: ScoreKey[] = ["s_slope", "s_lulc", "s_ghi", "s_power", "s_road", "s_temp"];
  const avgs = keys.map((k) => parcels.reduce((s, p) => s + (p[k] as number), 0) / n);

  return (
    <Bar
      data={{
        labels,
        datasets: [{
          label: "Average score",
          data: avgs,
          backgroundColor: FACTOR_COLORS.map((c) => `${c}CC`),
          borderColor: FACTOR_COLORS,
          borderWidth: 2,
          borderRadius: 5,
          borderSkipped: false,
          barThickness: 28,
        }],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            ...TOOLTIP_STYLE,
            callbacks: {
              label: (ctx) => `  Score: ${(ctx.parsed.y as number).toFixed(2)} / 4.0`,
            },
          },
        },
        scales: {
          y: {
            min: 0, max: 4,
            grid: { color: GRID_COLOR },
            ticks: { font: CHART_FONT, color: "#80868b", stepSize: 1 },
            border: { dash: [3, 3] },
          },
          x: {
            grid: { display: false },
            ticks: { font: { ...CHART_FONT, size: 10 }, color: "#5f6368", maxRotation: 0 },
          },
        },
      }}
    />
  );
}

// ─── LULC area distribution (Bare vs Shrubland) ───────────────────────────────
export function LULCAreaBars({ parcels }: { parcels: Parcel[] }) {
  const map: Record<string, number> = {};
  for (const p of parcels) {
    map[p.lulc] = (map[p.lulc] ?? 0) + p.area_ha;
  }
  const labels = Object.keys(map);
  const data   = labels.map((k) => map[k]);
  const colors = labels.map((l) => l === "Bare/sparse veg" ? "#a142f4" : "#0d8043");

  return (
    <Bar
      data={{
        labels,
        datasets: [{
          label: "Area (ha)",
          data,
          backgroundColor: colors.map((c) => `${c}BB`),
          borderColor: colors,
          borderWidth: 2,
          borderRadius: 6,
          borderSkipped: false,
          barThickness: 44,
        }],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            ...TOOLTIP_STYLE,
            callbacks: {
              label: (ctx) =>
                `  Area: ${(ctx.parsed.y as number).toLocaleString()} ha`,
            },
          },
        },
        scales: {
          y: {
            grid: { color: GRID_COLOR },
            ticks: { font: CHART_FONT, color: "#80868b" },
            border: { dash: [3, 3] },
            title: {
              display: true, text: "Area (ha)",
              font: { ...CHART_FONT, size: 10 }, color: "#80868b",
            },
          },
          x: {
            grid: { display: false },
            ticks: { font: { ...CHART_FONT, size: 10 }, color: "#5f6368", maxRotation: 0 },
          },
        },
      }}
    />
  );
}

// ─── GHI vs Suitability Score scatter ─────────────────────────────────────────
export function GHIScatter({ parcels }: { parcels: Parcel[] }) {
  // Sample max 500 points to keep chart responsive
  const sample = parcels.length > 500
    ? parcels.filter((_, i) => i % Math.ceil(parcels.length / 500) === 0)
    : parcels;

  const dataPoints = sample.map((p) => ({
    x: p.ghi,
    y: p.score,
    score: p.score,
  }));

  const getColor = (s: number) => {
    if (s >= 3.5)  return VH_COLOR;
    if (s >= 2.75) return H_COLOR;
    if (s >= 2.0)  return MOD_COLOR;
    return LOW_COLOR;
  };

  return (
    <Scatter
      data={{
        datasets: [{
          label: "Parcels",
          data: dataPoints,
          pointRadius: 3,
          pointHoverRadius: 5,
          pointBorderWidth: 0,
          backgroundColor: dataPoints.map((d) => `${getColor(d.score)}99`),
        }],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            ...TOOLTIP_STYLE,
            callbacks: {
              label: (ctx) => {
                const raw = ctx.raw as { x: number; y: number };
                return `  GHI: ${raw.x.toFixed(0)} kWh/m²/yr  Score: ${raw.y.toFixed(3)}`;
              },
            },
          },
        },
        scales: {
          x: {
            title: {
              display: true, text: "GHI (kWh/m²/yr)",
              font: { ...CHART_FONT, size: 10 }, color: "#80868b",
            },
            grid: { color: GRID_COLOR },
            ticks: { font: CHART_FONT, color: "#80868b" },
            border: { dash: [3, 3] },
          },
          y: {
            min: 0, max: 4,
            title: {
              display: true, text: "Suitability score",
              font: { ...CHART_FONT, size: 10 }, color: "#80868b",
            },
            grid: { color: GRID_COLOR },
            ticks: { font: CHART_FONT, color: "#80868b", stepSize: 1 },
            border: { dash: [3, 3] },
          },
        },
      }}
    />
  );
}

// ─── Slope vs Score scatter ───────────────────────────────────────────────────
export function SlopeScoreScatter({ parcels }: { parcels: Parcel[] }) {
  const sample = parcels.length > 400
    ? parcels.filter((_, i) => i % Math.ceil(parcels.length / 400) === 0)
    : parcels;

  const dataPoints = sample.map((p) => ({ x: p.slope, y: p.score, score: p.score }));
  const getColor = (s: number) =>
    s >= 3.5 ? VH_COLOR : s >= 2.75 ? H_COLOR : s >= 2.0 ? MOD_COLOR : LOW_COLOR;

  return (
    <Scatter
      data={{
        datasets: [{
          label: "Parcels",
          data: dataPoints,
          pointRadius: 3,
          pointHoverRadius: 5,
          pointBorderWidth: 0,
          backgroundColor: dataPoints.map((d) => `${getColor(d.score)}99`),
        }],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            ...TOOLTIP_STYLE,
            callbacks: {
              label: (ctx) => {
                const raw = ctx.raw as { x: number; y: number };
                return `  Slope: ${raw.x.toFixed(1)}°  Score: ${raw.y.toFixed(3)}`;
              },
            },
          },
        },
        scales: {
          x: {
            title: {
              display: true, text: "Slope (°)",
              font: { ...CHART_FONT, size: 10 }, color: "#80868b",
            },
            grid: { color: GRID_COLOR },
            ticks: { font: CHART_FONT, color: "#80868b" },
            border: { dash: [3, 3] },
          },
          y: {
            min: 0, max: 4,
            title: {
              display: true, text: "Suitability score",
              font: { ...CHART_FONT, size: 10 }, color: "#80868b",
            },
            grid: { color: GRID_COLOR },
            ticks: { font: CHART_FONT, color: "#80868b", stepSize: 1 },
            border: { dash: [3, 3] },
          },
        },
      }}
    />
  );
}
