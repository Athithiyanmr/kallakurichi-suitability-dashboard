import { useEffect, useMemo } from "react";
import { MapContainer, TileLayer, CircleMarker, Tooltip, useMap } from "react-leaflet";
import type { Parcel } from "../types";
import "leaflet/dist/leaflet.css";

function scoreColor(s: number): string {
  if (s >= 3.25) return "#15803d";
  if (s >= 2.5)  return "#16a34a";
  if (s >= 1.75) return "#d97706";
  return "#dc2626";
}
function scoreFill(s: number): string {
  if (s >= 3.25) return "#bbf7d0";
  if (s >= 2.5)  return "#dcfce7";
  if (s >= 1.75) return "#fef3c7";
  return "#fee2e2";
}
function scoreClass(s: number): string {
  if (s >= 3.25) return "Very High";
  if (s >= 2.5)  return "High";
  if (s >= 1.75) return "Moderate";
  return "Low";
}

function MapRecenter({ center }: { center: [number, number] }) {
  const map = useMap();
  useEffect(() => { map.setView(center, map.getZoom()); }, [center]);
  return null;
}

interface Props { parcels: Parcel[]; mapMode: "circles" | "heat"; }

const BASEMAPS = {
  "Light":     { url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
                 attr: "© OpenStreetMap © CARTO" },
  "Street":    { url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                 attr: "© OpenStreetMap contributors" },
  "Dark":      { url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
                 attr: "© OpenStreetMap © CARTO" },
  "Satellite": { url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                 attr: "Tiles © Esri" },
};

export function SuitabilityMap({ parcels, mapMode }: Props) {
  const center = useMemo<[number, number]>(() => {
    if (!parcels.length) return [11.85, 79.0];
    const la = parcels.reduce((s, p) => s + p.lat, 0) / parcels.length;
    const lo = parcels.reduce((s, p) => s + p.lon, 0) / parcels.length;
    return [la, lo];
  }, [parcels.length]);

  return (
    <div className="relative h-full">
      <MapContainer center={[11.85, 79.0]} zoom={10} style={{ height: "100%", width: "100%" }}
        zoomControl={true} scrollWheelZoom={true}>
        <TileLayer url={BASEMAPS["Light"].url} attribution={BASEMAPS["Light"].attr} />
        <MapRecenter center={center} />

        {parcels.map((p) => (
          <CircleMarker
            key={p.parcel_id}
            center={[p.lat, p.lon]}
            radius={7}
            pathOptions={{
              color: scoreColor(p.suitability_score),
              fillColor: scoreFill(p.suitability_score),
              fillOpacity: 0.82,
              weight: 1.5,
            }}
          >
            <Tooltip sticky>
              <div style={{ fontFamily: "DM Sans, sans-serif", minWidth: 200, fontSize: 12 }}>
                <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 4 }}>{p.parcel_id}</div>
                <div style={{ color: "#666", marginBottom: 6 }}>{p.village}</div>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  {[
                    ["Suitability", `${p.suitability_score.toFixed(3)} — ${scoreClass(p.suitability_score)}`],
                    ["Slope",       `${p.slope_score}/4 · ${p.slope_deg.toFixed(1)}°`],
                    ["LULC",        `${p.lulc_score}/4 · ${p.lulc_name}`],
                    ["Solar GHI",   `${p.ghi_score}/4 · ${p.ghi_kwh_m2_yr.toFixed(0)} kWh/m²/yr`],
                    ["PV Yield",    `${p.pv_yield_kwh_kwp.toFixed(0)} kWh/kWp/yr`],
                    ["Grid Dist.",  `${p.power_score}/4 · ${p.power_dist_km.toFixed(1)} km`],
                    ["Road Dist.",  `${p.road_score}/4 · ${p.road_dist_km.toFixed(1)} km`],
                    ["Temperature", `${p.temp_score}/4 · ${p.temp_c.toFixed(1)}°C`],
                    ["Elevation",   `${p.elevation_m.toFixed(0)} m`],
                    ["Coords",      `${p.lat.toFixed(4)}°N, ${p.lon.toFixed(4)}°E`],
                  ].map(([k, v]) => (
                    <tr key={k}>
                      <td style={{ color: "#888", padding: "2px 6px 2px 0", whiteSpace: "nowrap" }}>{k}</td>
                      <td style={{ textAlign: "right", padding: "2px 0", fontWeight: k === "Suitability" ? 700 : 400,
                                   color: k === "Suitability" ? scoreColor(p.suitability_score) : undefined }}>
                        {v}
                      </td>
                    </tr>
                  ))}
                </table>
              </div>
            </Tooltip>
          </CircleMarker>
        ))}
      </MapContainer>

      {/* Legend overlay */}
      <div className="absolute bottom-4 right-4 z-[1000] bg-card border border-border rounded-lg p-3 shadow-lg text-xs"
           style={{ backdropFilter: "blur(8px)", background: "hsla(0,0%,100%,0.92)" }}>
        <div className="font-semibold text-foreground mb-2 text-[11px] uppercase tracking-wide">Suitability</div>
        {[
          { color: "#15803d", label: "Very High  (3.25–4.0)" },
          { color: "#16a34a", label: "High       (2.50–3.25)" },
          { color: "#d97706", label: "Moderate   (1.75–2.50)" },
          { color: "#dc2626", label: "Low        (1.00–1.75)" },
        ].map(({ color, label }) => (
          <div key={label} className="flex items-center gap-2 mb-1">
            <div style={{ width: 10, height: 10, borderRadius: "50%", background: color }} />
            <span className="font-mono text-[11px]" style={{ color: "#444" }}>{label}</span>
          </div>
        ))}
      </div>

      {/* Source tag */}
      <div className="absolute bottom-4 left-4 z-[1000] text-[10px] font-medium px-2 py-1 rounded"
           style={{ background: "hsla(0,0%,100%,0.85)", color: "#666", backdropFilter: "blur(4px)" }}>
        Basemap: © OpenStreetMap / CARTO
      </div>
    </div>
  );
}
