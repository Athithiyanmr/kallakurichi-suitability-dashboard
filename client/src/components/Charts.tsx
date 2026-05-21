import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, ArcElement,
  Tooltip, Legend, Title, PointElement, LineElement,
} from "chart.js";
import { Bar, Doughnut, Scatter } from "react-chartjs-2";
import type { Parcel } from "../types";

ChartJS.register(
  CategoryScale, LinearScale, BarElement, ArcElement,
  Tooltip, Legend, Title, PointElement, LineElement
);

const CHART_FONT = { family: "DM Sans, system-ui, sans-serif", size: 11 };
const GRID_COLOR = "rgba(0,0,0,0.06)";

/* ── Suitability class doughnut ─────────────────────────────────────── */
export function SuitabilityDoughnut({ parcels }: { parcels: Parcel[] }) {
  const bins = { "Very High": 0, "High": 0, "Moderate": 0, "Low": 0 };
  parcels.forEach((p) => {
    if (p.suitability_score >= 3.25)      bins["Very High"]++;
    else if (p.suitability_score >= 2.5)  bins["High"]++;
    else if (p.suitability_score >= 1.75) bins["Moderate"]++;
    else                                  bins["Low"]++;
  });
  return (
    <Doughnut
      data={{
        labels: Object.keys(bins),
        datasets: [{
          data: Object.values(bins),
          backgroundColor: ["#15803d", "#16a34a", "#d97706", "#dc2626"],
          borderColor: "#fff",
          borderWidth: 2,
          hoverOffset: 6,
        }],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: true,
        cutout: "62%",
        plugins: {
          legend: { position: "bottom", labels: { font: CHART_FONT, boxWidth: 10, padding: 10 } },
          tooltip: { callbacks: {
            label: (ctx) => ` ${ctx.label}: ${ctx.parsed} (${Math.round(ctx.parsed/parcels.length*100)}%)`,
          }},
          title: { display: true, text: "Suitability Distribution", font: { ...CHART_FONT, size: 12, weight: "600" }, padding: { bottom: 8 } },
        },
      }}
    />
  );
}

/* ── Factor average bar chart ────────────────────────────────────────── */
export function FactorBars({ parcels }: { parcels: Parcel[] }) {
  const n = parcels.length || 1;
  const avgs = {
    Slope:  parcels.reduce((s, p) => s + p.slope_score, 0) / n,
    LULC:   parcels.reduce((s, p) => s + p.lulc_score, 0)  / n,
    GHI:    parcels.reduce((s, p) => s + p.ghi_score, 0)   / n,
    Grid:   parcels.reduce((s, p) => s + p.power_score, 0) / n,
    Road:   parcels.reduce((s, p) => s + p.road_score, 0)  / n,
    Temp:   parcels.reduce((s, p) => s + p.temp_score, 0)  / n,
  };
  return (
    <Bar
      data={{
        labels: Object.keys(avgs),
        datasets: [{
          label: "Avg Score",
          data: Object.values(avgs),
          backgroundColor: ["#64748b", "#16a34a", "#d97706", "#0891b2", "#7c3aed", "#dc2626"],
          borderRadius: 4,
          borderSkipped: false,
        }],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: true,
        scales: {
          y: { min: 0, max: 4, ticks: { font: CHART_FONT, stepSize: 1 }, grid: { color: GRID_COLOR },
               title: { display: true, text: "Score (1–4)", font: CHART_FONT } },
          x: { ticks: { font: CHART_FONT }, grid: { display: false } },
        },
        plugins: {
          legend: { display: false },
          title: { display: true, text: "Average Factor Scores", font: { ...CHART_FONT, size: 12, weight: "600" }, padding: { bottom: 8 } },
          tooltip: { callbacks: { label: (ctx) => ` ${ctx.parsed.y.toFixed(2)} / 4.0` } },
        },
      }}
    />
  );
}

/* ── Village comparison bar ──────────────────────────────────────────── */
export function VillageBars({ parcels }: { parcels: Parcel[] }) {
  const vmap: Record<string, number[]> = {};
  parcels.forEach((p) => {
    if (!vmap[p.village]) vmap[p.village] = [];
    vmap[p.village].push(p.suitability_score);
  });
  const sorted = Object.entries(vmap)
    .map(([v, scores]) => ({ v, avg: scores.reduce((a, b) => a + b, 0) / scores.length, n: scores.length }))
    .sort((a, b) => b.avg - a.avg);

  return (
    <Bar
      data={{
        labels: sorted.map((s) => s.v),
        datasets: [{
          label: "Avg Suitability",
          data: sorted.map((s) => s.avg),
          backgroundColor: sorted.map((s) =>
            s.avg >= 3.25 ? "#15803d" : s.avg >= 2.5 ? "#16a34a" : s.avg >= 1.75 ? "#d97706" : "#dc2626"
          ),
          borderRadius: 4,
          borderSkipped: false,
        }],
      }}
      options={{
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { min: 0, max: 4, ticks: { font: CHART_FONT }, grid: { color: GRID_COLOR },
               title: { display: true, text: "Avg Suitability Score", font: CHART_FONT } },
          y: { ticks: { font: CHART_FONT }, grid: { display: false } },
        },
        plugins: {
          legend: { display: false },
          title: { display: true, text: "Village-Level Comparison", font: { ...CHART_FONT, size: 12, weight: "600" }, padding: { bottom: 8 } },
          tooltip: { callbacks: {
            label: (ctx) => ` ${(ctx.parsed.x as number).toFixed(3)} — ${sorted[ctx.dataIndex].n} parcels`,
          }},
        },
      }}
    />
  );
}

/* ── GHI vs Suitability scatter ──────────────────────────────────────── */
export function GHIScatter({ parcels }: { parcels: Parcel[] }) {
  const data = parcels.slice(0, 200).map((p) => ({
    x: p.ghi_kwh_m2_yr,
    y: p.suitability_score,
  }));
  return (
    <Scatter
      data={{
        datasets: [{
          label: "GHI vs Score",
          data,
          pointBackgroundColor: parcels.slice(0, 200).map((p) =>
            p.suitability_score >= 3.25 ? "#15803d" :
            p.suitability_score >= 2.5  ? "#16a34a" :
            p.suitability_score >= 1.75 ? "#d97706" : "#dc2626"
          ),
          pointRadius: 4, pointHoverRadius: 6,
          borderColor: "transparent",
        }],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: true,
        scales: {
          x: { ticks: { font: CHART_FONT }, grid: { color: GRID_COLOR },
               title: { display: true, text: "GHI (kWh/m²/yr) — PVGIS ERA5", font: CHART_FONT } },
          y: { min: 1, max: 4, ticks: { font: CHART_FONT }, grid: { color: GRID_COLOR },
               title: { display: true, text: "Suitability Score", font: CHART_FONT } },
        },
        plugins: {
          legend: { display: false },
          title: { display: true, text: "GHI vs Suitability Score", font: { ...CHART_FONT, size: 12, weight: "600" }, padding: { bottom: 8 } },
        },
      }}
    />
  );
}
