import { ExternalLink, Database, Globe, Satellite, Zap, Route, Thermometer } from "lucide-react";

interface Source {
  id: string;
  name: string;
  shortName: string;
  description: string;
  resolution: string;
  period: string;
  coverage: string;
  url: string;
  license: string;
  icon: typeof Database;
  color: string;
  factor: string;
}

const SOURCES: Source[] = [
  {
    id: "esa",
    name: "ESA WorldCover 2020 v100",
    shortName: "ESA WorldCover",
    description:
      "Global land cover map at 10 m resolution based on Sentinel-1 and Sentinel-2 data. Provides 11 LULC classes used to determine parcel land suitability.",
    resolution: "10 m",
    period: "2020",
    coverage: "Global",
    url: "https://worldcover2020.esa.int/",
    license: "CC BY 4.0",
    icon: Satellite,
    color: "hsl(141 55% 28%)",
    factor: "LULC Score",
  },
  {
    id: "srtm",
    name: "NASA SRTM 30 m (OpenTopoData)",
    shortName: "NASA SRTM",
    description:
      "Shuttle Radar Topography Mission digital elevation model. Elevation values are used to derive slope in degrees via finite difference gradient, applied to penalise steep terrain.",
    resolution: "30 m (~1 arc-sec)",
    period: "2000",
    coverage: "Global (60°N–56°S)",
    url: "https://www.opentopodata.org/",
    license: "Public Domain",
    icon: Globe,
    color: "hsl(199 78% 24%)",
    factor: "Slope Score",
  },
  {
    id: "pvgis",
    name: "PVGIS 5.2 — ERA5 Reanalysis",
    shortName: "PVGIS ERA5",
    description:
      "European Commission photovoltaic geographical information system. Provides long-term annual GHI (Global Horizontal Irradiance) computed from ERA5 reanalysis data over 1985–2020.",
    resolution: "~5 km grid",
    period: "1985–2020",
    coverage: "Europe / Africa / Asia",
    url: "https://re.jrc.ec.europa.eu/pvg_tools/en/",
    license: "CC BY 4.0 — European Commission",
    icon: Zap,
    color: "hsl(38 95% 48%)",
    factor: "GHI Score",
  },
  {
    id: "power",
    name: "NASA POWER v8 — MERRA-2",
    shortName: "NASA POWER",
    description:
      "Prediction of Worldwide Energy Resources — daily meteorological data derived from MERRA-2 atmospheric reanalysis. Used for near-surface temperature validation and cross-check GHI.",
    resolution: "0.5° × 0.625°",
    period: "1984–present",
    coverage: "Global",
    url: "https://power.larc.nasa.gov/",
    license: "Public Domain",
    icon: Thermometer,
    color: "hsl(0 72% 51%)",
    factor: "Temperature Score",
  },
  {
    id: "osm-power",
    name: "OpenStreetMap — Power Infrastructure",
    shortName: "OSM Power Lines",
    description:
      "Crowdsourced power line and substation data from OpenStreetMap via Overpass API. Euclidean distance from each parcel centroid to the nearest HV/MV power line node.",
    resolution: "Node-level",
    period: "2024",
    coverage: "Kallakurichi district",
    url: "https://overpass-api.de/",
    license: "ODbL 1.0",
    icon: Zap,
    color: "hsl(220 24% 14%)",
    factor: "Grid Distance Score",
  },
  {
    id: "osm-roads",
    name: "OpenStreetMap — Road Network",
    shortName: "OSM Highways",
    description:
      "Road geometry including primary, secondary, tertiary, and unclassified highways from OSM. Euclidean distance to the nearest road node determines accessibility score.",
    resolution: "Node-level",
    period: "2024",
    coverage: "Kallakurichi district",
    url: "https://overpass-api.de/",
    license: "ODbL 1.0",
    icon: Route,
    color: "hsl(220 20% 40%)",
    factor: "Road Distance Score",
  },
];

const METHODOLOGY_STEPS = [
  {
    step: "01",
    title: "Grid Generation",
    detail:
      "400 evenly-distributed sample points generated across Kallakurichi district bounding box (11.6–12.2°N, 78.6–79.2°E) using a 20×20 grid.",
  },
  {
    step: "02",
    title: "Spatial Interpolation",
    detail:
      "KD-tree nearest-neighbour lookup used to match each grid point to the closest sampled observation from each raw data source.",
  },
  {
    step: "03",
    title: "Factor Scoring",
    detail:
      "Each factor scored 1–4 using a rubric (e.g. slope <3° → 4, LULC bare/sparse → 4, GHI ≥1980 kWh/m²/yr → 4). Scores are ordinal, not continuous.",
  },
  {
    step: "04",
    title: "Weighted Overlay",
    detail:
      "User-defined weights (0–10) normalised to sum=1. Composite score = Σ(weight_i × score_i). Range 1–4. Computed live on the Express API.",
  },
  {
    step: "05",
    title: "Classification",
    detail:
      "Composite score binned: ≥3.5 → Very High, ≥2.75 → High, ≥2.0 → Moderate, <2.0 → Low. Class thresholds independent of weight settings.",
  },
];

const SCORE_RUBRIC = [
  { factor: "Slope", s1: ">15°", s2: "8–15°", s3: "3–8°", s4: "<3°" },
  { factor: "LULC", s1: "Built-up / Water", s2: "Tree / Wetland", s3: "Cropland / Shrub", s4: "Bare / Sparse" },
  { factor: "GHI", s1: "<1950 kWh", s2: "1950–1965", s3: "1965–1980", s4: "≥1980 kWh" },
  { factor: "Grid Dist.", s1: ">10 km", s2: "5–10 km", s3: "2–5 km", s4: "≤2 km" },
  { factor: "Road Dist.", s1: ">8 km", s2: "3–8 km", s3: "1–3 km", s4: "≤1 km" },
  { factor: "Temperature", s1: ">27 °C", s2: "26–27 °C", s3: "25–26 °C", s4: "≤25 °C" },
];

const SCORE_COLORS = ["hsl(0 72% 55%)", "hsl(38 90% 50%)", "hsl(142 45% 40%)", "hsl(141 55% 28%)"];
const SCORE_LABELS = ["Low", "Moderate", "High", "Very High"];

export default function DataSources() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div>
        <h2
          style={{
            fontSize: "16px",
            fontWeight: 700,
            color: "hsl(var(--foreground))",
            marginBottom: "4px",
            letterSpacing: "-0.02em",
          }}
        >
          Data Provenance & Methodology
        </h2>
        <p style={{ fontSize: "13px", color: "hsl(var(--muted-foreground))", margin: 0 }}>
          All datasets are from public, peer-reviewed or government sources. Processing scripts are available on GitHub.
        </p>
      </div>

      {/* ── Source Cards ─────────────────────────────────────────────────────── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: "12px",
        }}
      >
        {SOURCES.map((src) => {
          const Icon = src.icon;
          return (
            <div
              key={src.id}
              style={{
                background: "hsl(var(--card))",
                border: "1px solid hsl(var(--border))",
                borderRadius: "10px",
                padding: "16px",
                display: "flex",
                flexDirection: "column",
                gap: "10px",
              }}
            >
              {/* Card header */}
              <div style={{ display: "flex", alignItems: "flex-start", gap: "10px" }}>
                <div
                  style={{
                    width: "32px",
                    height: "32px",
                    borderRadius: "7px",
                    background: `${src.color}18`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  <Icon size={16} style={{ color: src.color }} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: "12px", fontWeight: 700, color: "hsl(var(--foreground))", lineHeight: 1.3 }}>
                    {src.shortName}
                  </div>
                  <div
                    style={{
                      marginTop: "3px",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "4px",
                      fontSize: "10px",
                      fontWeight: 600,
                      color: src.color,
                      background: `${src.color}18`,
                      padding: "2px 7px",
                      borderRadius: "20px",
                    }}
                  >
                    {src.factor}
                  </div>
                </div>
              </div>

              {/* Description */}
              <p style={{ fontSize: "11.5px", color: "hsl(var(--muted-foreground))", lineHeight: 1.6, margin: 0 }}>
                {src.description}
              </p>

              {/* Meta grid */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "6px",
                  paddingTop: "8px",
                  borderTop: "1px solid hsl(var(--border))",
                }}
              >
                {[
                  ["Resolution", src.resolution],
                  ["Period", src.period],
                  ["Coverage", src.coverage],
                  ["License", src.license],
                ].map(([label, val]) => (
                  <div key={label}>
                    <div style={{ fontSize: "9px", fontWeight: 600, color: "hsl(var(--muted-foreground))", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                      {label}
                    </div>
                    <div style={{ fontSize: "11px", color: "hsl(var(--foreground))", fontWeight: 500, marginTop: "1px" }}>
                      {val}
                    </div>
                  </div>
                ))}
              </div>

              {/* Link */}
              <a
                href={src.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "5px",
                  fontSize: "11px",
                  fontWeight: 600,
                  color: "hsl(var(--primary))",
                  textDecoration: "none",
                }}
              >
                <ExternalLink size={11} />
                {src.url.replace("https://", "").replace(/\/$/, "")}
              </a>
            </div>
          );
        })}
      </div>

      {/* ── Methodology Steps ────────────────────────────────────────────────── */}
      <div
        style={{
          background: "hsl(var(--card))",
          border: "1px solid hsl(var(--border))",
          borderRadius: "10px",
          padding: "20px",
        }}
      >
        <h3 style={{ fontSize: "13px", fontWeight: 700, color: "hsl(var(--foreground))", marginBottom: "16px" }}>
          Processing Pipeline
        </h3>
        <div style={{ display: "flex", gap: "0", position: "relative" }}>
          {/* connecting line */}
          <div
            style={{
              position: "absolute",
              top: "16px",
              left: "16px",
              right: "16px",
              height: "1px",
              background: "hsl(var(--border))",
              zIndex: 0,
            }}
          />
          {METHODOLOGY_STEPS.map((s, i) => (
            <div
              key={s.step}
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                padding: "0 8px",
                zIndex: 1,
              }}
            >
              <div
                style={{
                  width: "32px",
                  height: "32px",
                  borderRadius: "50%",
                  background: "hsl(var(--primary))",
                  color: "hsl(var(--primary-foreground))",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "11px",
                  fontWeight: 700,
                  marginBottom: "10px",
                  flexShrink: 0,
                  fontFamily: "JetBrains Mono, monospace",
                }}
              >
                {s.step}
              </div>
              <div style={{ fontSize: "11px", fontWeight: 700, color: "hsl(var(--foreground))", textAlign: "center", marginBottom: "6px" }}>
                {s.title}
              </div>
              <p style={{ fontSize: "10.5px", color: "hsl(var(--muted-foreground))", textAlign: "center", lineHeight: 1.55, margin: 0 }}>
                {s.detail}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Scoring Rubric ───────────────────────────────────────────────────── */}
      <div
        style={{
          background: "hsl(var(--card))",
          border: "1px solid hsl(var(--border))",
          borderRadius: "10px",
          padding: "20px",
        }}
      >
        <h3 style={{ fontSize: "13px", fontWeight: 700, color: "hsl(var(--foreground))", marginBottom: "16px" }}>
          Factor Scoring Rubric (1 – 4 Scale)
        </h3>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
            <thead>
              <tr>
                <th
                  style={{
                    textAlign: "left",
                    padding: "8px 12px",
                    fontSize: "10px",
                    fontWeight: 700,
                    color: "hsl(var(--muted-foreground))",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    borderBottom: "1px solid hsl(var(--border))",
                  }}
                >
                  Factor
                </th>
                {[1, 2, 3, 4].map((score, i) => (
                  <th
                    key={score}
                    style={{
                      textAlign: "center",
                      padding: "8px 12px",
                      borderBottom: "1px solid hsl(var(--border))",
                    }}
                  >
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "4px",
                        fontSize: "10px",
                        fontWeight: 700,
                        color: SCORE_COLORS[i],
                        background: `${SCORE_COLORS[i]}18`,
                        padding: "2px 8px",
                        borderRadius: "20px",
                      }}
                    >
                      {score} — {SCORE_LABELS[i]}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {SCORE_RUBRIC.map((row, idx) => (
                <tr
                  key={row.factor}
                  style={{ background: idx % 2 === 0 ? "transparent" : "hsl(var(--muted) / 0.3)" }}
                >
                  <td
                    style={{
                      padding: "9px 12px",
                      fontWeight: 600,
                      color: "hsl(var(--foreground))",
                      fontSize: "12px",
                    }}
                  >
                    {row.factor}
                  </td>
                  {[row.s1, row.s2, row.s3, row.s4].map((cell, ci) => (
                    <td
                      key={ci}
                      style={{
                        padding: "9px 12px",
                        textAlign: "center",
                        color: "hsl(var(--muted-foreground))",
                        fontSize: "11.5px",
                      }}
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── GitHub link ─────────────────────────────────────────────────────── */}
      <div
        style={{
          background: "hsl(var(--primary) / 0.06)",
          border: "1px solid hsl(var(--primary) / 0.2)",
          borderRadius: "10px",
          padding: "16px 20px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "16px",
        }}
      >
        <div>
          <div style={{ fontSize: "13px", fontWeight: 700, color: "hsl(var(--foreground))" }}>
            Open Source — Full Processing Pipeline on GitHub
          </div>
          <div style={{ fontSize: "12px", color: "hsl(var(--muted-foreground))", marginTop: "2px" }}>
            5 reproducible Python scripts: data fetch → interpolation → scoring → export. MIT license.
          </div>
        </div>
        <a
          href="https://github.com/Athithiyanmr/kallakurichi-suitability-dashboard"
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            padding: "8px 16px",
            borderRadius: "7px",
            background: "hsl(var(--primary))",
            color: "hsl(var(--primary-foreground))",
            fontSize: "12px",
            fontWeight: 600,
            textDecoration: "none",
            flexShrink: 0,
          }}
        >
          <ExternalLink size={12} />
          View on GitHub
        </a>
      </div>
    </div>
  );
}
