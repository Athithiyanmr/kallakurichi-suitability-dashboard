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

// ─── Google-matching palette ──────────────────────────────────────────────────
const G_BLUE   = "#4285f4";
const G_GREEN  = "#34a853";
const G_AMBER  = "#fbbc04";
const G_RED    = "#ea4335";
const G_PURPLE = "#a142f4";
const G_SLATE  = "#5f6368";

const SCORE_COLORS = [G_GREEN, "#0f9d58", G_AMBER, G_RED];
const FACTOR_COLORS = [G_SLATE, G_GREEN, G_AMBER, G_BLUE, G_PURPLE, G_RED];

const CHART_FONT = { family: "'Inter', system-ui, sans-serif", size: 11 };
const GRID_COLOR = "rgba(0,0,0,0.05)";

const TOOLTIP_STYLE = {
  backgroundColor: "rgba(32,33,36,0.92)",
  titleColor: "#fff",
  bodyColor: "#bdc1c6",
  borderColor: "transparent",
  cornerRadius: 8,
  padding: 10,
  titleFont: { ...CHART_FONT, weight: "600" },
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
    if      (p.suitability_score >= 3.25) bins["Very High"]++;
    else if (p.suitability_score >= 2.5)  bins["High"]++;
    else if (p.suitability_score >= 1.75) bins["Moderate"]++;
    else                                   bins["Low"]++;
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
              boxWidth: 10,
              boxHeight: 10,
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

// ─── Factor Bars ──────────────────────────────────────────────────────────────
export function FactorBars({ parcels }: { parcels: Parcel[] }) {
  const n = parcels.length || 1;
  const labels = ["Slope", "Land Cover", "Solar GHI", "Grid Access", "Road Access", "Temperature"];
  const keys: Array<keyof Parcel> = [
    "slope_score", "lulc_score", "ghi_score", "power_score", "road_score", "temp_score",
  ];
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

// ─── Village Bars ─────────────────────────────────────────────────────────────
export function VillageBars({ parcels }: { parcels: Parcel[] }) {
  const map: Record<string, number[]> = {};
  for (const p of parcels) {
    (map[p.village] = map[p.village] ?? []).push(p.suitability_score);
  }
  const entries = Object.entries(map)
    .map(([v, scores]) => ({ v, avg: scores.reduce((a, b) => a + b, 0) / scores.length }))
    .sort((a, b) => b.avg - a.avg)
    .slice(0, 8);

  return (
    <Bar
      data={{
        labels: entries.map((e) => e.v),
        datasets: [{
          label: "Avg score",
          data: entries.map((e) => e.avg),
          backgroundColor: G_BLUE + "BB",
          borderColor: G_BLUE,
          borderWidth: 2,
          borderRadius: 5,
          borderSkipped: false,
          barThickness: 18,
        }],
      }}
      options={{
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            ...TOOLTIP_STYLE,
            callbacks: {
              label: (ctx) => `  Score: ${(ctx.parsed.x as number).toFixed(3)}`,
            },
          },
        },
        scales: {
          x: {
            min: 0, max: 4,
            grid: { color: GRID_COLOR },
            ticks: { font: CHART_FONT, color: "#80868b", stepSize: 1 },
            border: { dash: [3, 3] },
          },
          y: {
            grid: { display: false },
            ticks: { font: { ...CHART_FONT, size: 10 }, color: "#5f6368" },
          },
        },
      }}
    />
  );
}

// ─── GHI Scatter ──────────────────────────────────────────────────────────────
export function GHIScatter({ parcels }: { parcels: Parcel[] }) {
  // Colour-code by suitability score
  const dataPoints = parcels.map((p) => ({
    x: p.ghi_kwh_m2_yr,
    y: p.suitability_score,
    score: p.suitability_score,
  }));

  const getColor = (s: number) => {
    if (s >= 3.25) return "#0f9d58";
    if (s >= 2.5)  return G_GREEN;
    if (s >= 1.75) return G_AMBER;
    return G_RED;
  };

  return (
    <Scatter
      data={{
        datasets: [{
          label: "Parcels",
          data: dataPoints,
          pointRadius: 4,
          pointHoverRadius: 6,
          pointBorderWidth: 0,
          backgroundColor: dataPoints.map((d) => `${getColor(d.score)}AA`),
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
              display: true,
              text: "GHI (kWh/m²/yr)",
              font: { ...CHART_FONT, size: 10 },
              color: "#80868b",
            },
            grid: { color: GRID_COLOR },
            ticks: { font: CHART_FONT, color: "#80868b" },
            border: { dash: [3, 3] },
          },
          y: {
            min: 0, max: 4,
            title: {
              display: true,
              text: "Suitability score",
              font: { ...CHART_FONT, size: 10 },
              color: "#80868b",
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
