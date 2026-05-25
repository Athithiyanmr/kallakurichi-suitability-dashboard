import { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Tooltip, useMap } from "react-leaflet";
import type { Parcel } from "../types";
import "leaflet/dist/leaflet.css";

// ─── Score colour helpers ─────────────────────────────────────────────────────
function scoreLine(s: number): string {
  if (s >= 3.25) return "#0f9d58";
  if (s >= 2.5)  return "#34a853";
  if (s >= 1.75) return "#f4b400";
  return "#ea4335";
}
function scoreFill(s: number): string {
  if (s >= 3.25) return "#ceead6";
  if (s >= 2.5)  return "#e6f4ea";
  if (s >= 1.75) return "#fef3c7";
  return "#fce8e6";
}
function scoreLabel(s: number): string {
  if (s >= 3.25) return "Very High";
  if (s >= 2.5)  return "High";
  if (s >= 1.75) return "Moderate";
  return "Low";
}
function scoreBadgeClass(s: number): string {
  if (s >= 3.25) return "badge-score badge-vh";
  if (s >= 2.5)  return "badge-score badge-h";
  if (s >= 1.75) return "badge-score badge-mod";
  return "badge-score badge-low";
}

// ─── Basemap definitions ──────────────────────────────────────────────────────
const BASEMAPS: Record<string, { url: string; attr: string }> = {
  "Light":     { url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",    attr: "© OpenStreetMap © CARTO" },
  "Street":    { url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",                     attr: "© OpenStreetMap contributors" },
  "Satellite": { url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", attr: "Tiles © Esri" },
  "Terrain":   { url: "https://stamen-tiles-{s}.a.ssl.fastly.net/terrain/{z}/{x}/{y}.png",  attr: "© Stamen Design, © OpenStreetMap" },
};

// ─── Map recentrer ────────────────────────────────────────────────────────────
function MapRecenter({ center }: { center: [number, number] }) {
  const map = useMap();
  useEffect(() => { map.setView(center, map.getZoom()); }, [center]);
  return null;
}

// ─── Floating overlay cards ───────────────────────────────────────────────────
function MapLegend() {
  return (
    <div className="map-overlay map-legend" style={{ minWidth: 130 }}>
      <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", color: "hsl(var(--foreground-tertiary))", marginBottom: 8 }}>
        Suitability
      </div>
      {[
        { label: "Very High (≥ 3.25)", color: "#0f9d58" },
        { label: "High (≥ 2.50)",      color: "#34a853" },
        { label: "Moderate (≥ 1.75)",  color: "#f4b400" },
        { label: "Low (< 1.75)",       color: "#ea4335" },
      ].map(({ label, color }) => (
        <div className="legend-row" key={label}>
          <span className="legend-dot" style={{ background: color }} />
          <span style={{ fontSize: 11 }}>{label}</span>
        </div>
      ))}
    </div>
  );
}

function BasemapSelector({ active, onChange }: {
  active: string;
  onChange: (name: string) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="map-overlay map-basemap" style={{ minWidth: 100 }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: "100%", background: "none", border: "none", cursor: "pointer",
          fontSize: 11, fontWeight: 600, color: "hsl(var(--foreground))",
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6,
          padding: 0,
        }}
      >
        <span>🗺 {active}</span>
        <span style={{ opacity: 0.5 }}>{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div style={{ marginTop: 6 }}>
          {Object.keys(BASEMAPS).map((name) => (
            <button
              key={name}
              className={`basemap-btn${active === name ? " active" : ""}`}
              onClick={() => { onChange(name); setOpen(false); }}
            >
              {name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function MapStats({ parcels }: { parcels: Parcel[] }) {
  const n = parcels.length;
  if (!n) return null;
  const counts = {
    "Very High": parcels.filter((p) => p.suitability_score >= 3.25).length,
    "High":      parcels.filter((p) => p.suitability_score >= 2.5 && p.suitability_score < 3.25).length,
    "Moderate":  parcels.filter((p) => p.suitability_score >= 1.75 && p.suitability_score < 2.5).length,
    "Low":       parcels.filter((p) => p.suitability_score < 1.75).length,
  };
  return (
    <div className="map-overlay map-stats" style={{ minWidth: 152 }}>
      <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", color: "hsl(var(--foreground-tertiary))", marginBottom: 6 }}>
        {n.toLocaleString()} parcels shown
      </div>
      {Object.entries(counts).map(([label, cnt]) => {
        const colors: Record<string, string> = {
          "Very High": "#0f9d58", "High": "#34a853", "Moderate": "#f4b400", "Low": "#ea4335",
        };
        const pct = ((cnt / n) * 100).toFixed(0);
        return (
          <div key={label} style={{ marginBottom: 4 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 2 }}>
              <span style={{ color: "hsl(var(--foreground))", fontWeight: 500 }}>{label}</span>
              <span style={{ color: "hsl(var(--foreground-secondary))", fontFamily: "monospace", fontSize: 10 }}>
                {cnt.toLocaleString()} ({pct}%)
              </span>
            </div>
            <div style={{ height: 3, borderRadius: 2, background: "hsl(var(--border))" }}>
              <div style={{ height: "100%", borderRadius: 2, width: `${pct}%`, background: colors[label], transition: "width 0.4s" }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── Tooltip content ─────────────────────────────────────────────────────────
function ParcelTooltip({ p }: { p: Parcel }) {
  return (
    <div style={{ fontFamily: "'Inter', sans-serif", minWidth: 210, fontSize: 12, padding: 2 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <span style={{ fontWeight: 700, fontSize: 13, color: "hsl(214 32% 12%)" }}>{p.parcel_id}</span>
        <span className={scoreBadgeClass(p.suitability_score)} style={{ fontSize: 10 }}>
          {scoreLabel(p.suitability_score)}
        </span>
      </div>
      <div style={{ fontSize: 11, color: "#5f6368", marginBottom: 8, fontWeight: 500 }}>{p.village}</div>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <tbody>
          {([
            ["Score",       `${p.suitability_score.toFixed(3)} / 4.00`],
            ["GHI",         `${p.ghi_kwh_m2_yr.toFixed(0)} kWh/m²/yr`],
            ["PV Yield",    `${p.pv_yield_kwh_kwp.toFixed(0)} kWh/kWp/yr`],
            ["Slope",       `${p.slope_deg.toFixed(1)}°`],
            ["Land Cover",  p.lulc_name],
            ["Grid Dist.",  `${p.power_dist_km.toFixed(1)} km`],
            ["Road Dist.",  `${p.road_dist_km.toFixed(1)} km`],
            ["Elevation",   `${p.elevation_m.toFixed(0)} m`],
            ["Temperature", `${p.temp_c.toFixed(1)} °C`],
          ] as [string, string][]).map(([k, v]) => (
            <tr key={k}>
              <td style={{ color: "#80868b", padding: "2px 8px 2px 0", fontSize: 11, whiteSpace: "nowrap" }}>{k}</td>
              <td style={{
                textAlign: "right", padding: "2px 0", fontSize: 11,
                fontWeight: k === "Score" ? 700 : 400,
                color: k === "Score" ? scoreLine(p.suitability_score) : "hsl(214 32% 12%)",
                fontFamily: "monospace",
              }}>
                {v}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ marginTop: 8, fontSize: 10, color: "#bdc1c6", fontFamily: "monospace" }}>
        {p.lat.toFixed(5)}°N  {p.lon.toFixed(5)}°E
      </div>
    </div>
  );
}

// ─── Main map component ───────────────────────────────────────────────────────
interface Props { parcels: Parcel[]; mapMode: "circles" | "heat"; }

export function SuitabilityMap({ parcels }: Props) {
  const [basemap, setBasemap] = useState<string>("Light");

  const center = useMemo<[number, number]>(() => {
    if (!parcels.length) return [11.85, 79.0];
    const la = parcels.reduce((s, p) => s + p.lat, 0) / parcels.length;
    const lo = parcels.reduce((s, p) => s + p.lon, 0) / parcels.length;
    return [la, lo];
  }, [parcels.length]);

  const { url, attr } = BASEMAPS[basemap];

  return (
    <div style={{
      flex: 1,
      margin: "0 24px 20px",
      position: "relative",
      borderRadius: "var(--radius-lg)",
      overflow: "hidden",
      border: "1px solid hsl(var(--border))",
      boxShadow: "var(--shadow-1)",
    }}>
      <MapContainer
        center={[11.85, 79.0]}
        zoom={10}
        style={{ width: "100%", height: "100%" }}
        scrollWheelZoom
        zoomControl
      >
        <TileLayer url={url} attribution={attr} key={basemap} />
        <MapRecenter center={center} />

        {parcels.map((p) => (
          <CircleMarker
            key={p.parcel_id}
            center={[p.lat, p.lon]}
            radius={6}
            pathOptions={{
              color:       scoreLine(p.suitability_score),
              fillColor:   scoreFill(p.suitability_score),
              fillOpacity: 0.85,
              weight:      1.5,
            }}
          >
            <Tooltip sticky>
              <ParcelTooltip p={p} />
            </Tooltip>
          </CircleMarker>
        ))}
      </MapContainer>

      {/* Floating overlays */}
      <MapStats   parcels={parcels} />
      <BasemapSelector active={basemap} onChange={setBasemap} />
      <MapLegend />
    </div>
  );
}
