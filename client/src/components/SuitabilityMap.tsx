import { useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, TileLayer, useMap, GeoJSON } from "react-leaflet";
import type { FeatureCollection, Feature } from "geojson";
import type { PathOptions, Layer, LeafletMouseEvent } from "leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Parcel, Weights, Filters } from "../types";
import { buildGeoJSONUrl } from "../hooks/useParcels";
import { apiRequest } from "../lib/queryClient";
import { Layers } from "lucide-react";

// ─── Score color helpers ──────────────────────────────────────────────────────
function scoreStroke(s: number): string {
  if (s >= 3.5) return "#0d8043";
  if (s >= 2.75) return "#1a73e8";
  if (s >= 2.0) return "#e37400";
  return "#c5221f";
}
function scoreFill(s: number): string {
  if (s >= 3.5) return "#ceead6";
  if (s >= 2.75) return "#d2e3fc";
  if (s >= 2.0) return "#fce8b2";
  return "#fce8e6";
}
function scoreLabel(s: number): string {
  if (s >= 3.5) return "Very High";
  if (s >= 2.75) return "High";
  if (s >= 2.0) return "Moderate";
  return "Low";
}
function badgeClass(s: number): string {
  if (s >= 3.5) return "badge-vh";
  if (s >= 2.75) return "badge-h";
  if (s >= 2.0) return "badge-mod";
  return "badge-low";
}
function lulcIcon(lulc: string): string {
  return lulc === "Bare/sparse veg" ? "🟤" : "🟢";
}

// ─── Basemap definitions ──────────────────────────────────────────────────────
const BASEMAPS: Record<string, { url: string; attr: string }> = {
  "Light":     { url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",     attr: "© OpenStreetMap © CARTO" },
  "Street":    { url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",                      attr: "© OpenStreetMap contributors" },
  "Satellite": { url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", attr: "Tiles © Esri" },
  "Terrain":   { url: "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",                    attr: "© OpenTopoMap" },
};

// ─── Fit-to-bounds helper ─────────────────────────────────────────────────────
function FitBounds({ geojson }: { geojson: FeatureCollection | null }) {
  const map = useMap();
  useEffect(() => {
    if (!geojson || !geojson.features?.length) return;
    try {
      const layer = L.geoJSON(geojson);
      const bounds = layer.getBounds();
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [24, 24] });
      }
    } catch {
      map.setView([11.85, 79.0], 9);
    }
  }, [geojson]);
  return null;
}

// ─── Floating overlay: legend ─────────────────────────────────────────────────
function MapLegend() {
  return (
    <div className="map-overlay map-legend" style={{ minWidth: 148 }}>
      <div className="overlay-label">Suitability</div>
      {[
        { label: "Very High (≥ 3.50)", stroke: "#0d8043", fill: "#ceead6" },
        { label: "High (≥ 2.75)",      stroke: "#1a73e8", fill: "#d2e3fc" },
        { label: "Moderate (≥ 2.00)",  stroke: "#e37400", fill: "#fce8b2" },
        { label: "Low (< 2.00)",       stroke: "#c5221f", fill: "#fce8e6" },
      ].map(({ label, stroke, fill }) => (
        <div className="legend-row" key={label}>
          <span className="legend-swatch" style={{ background: fill, border: `1.5px solid ${stroke}` }} />
          <span>{label}</span>
        </div>
      ))}
      <div className="overlay-label" style={{ marginTop: 10 }}>Land Cover</div>
      <div className="legend-row"><span>🟤</span><span>Bare / sparse veg</span></div>
      <div className="legend-row"><span>🟢</span><span>Shrubland</span></div>
    </div>
  );
}

// ─── Floating overlay: basemap picker ─────────────────────────────────────────
function BasemapSelector({ active, onChange }: { active: string; onChange: (n: string) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="map-overlay map-basemap" style={{ minWidth: 110 }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: "100%", background: "none", border: "none", cursor: "pointer",
          fontSize: 11, fontWeight: 600, color: "hsl(var(--foreground))",
          display: "flex", alignItems: "center", justifyContent: "space-between", padding: 0,
        }}
      >
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <Layers size={11} /> {active}
        </span>
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

// ─── Floating overlay: stats panel ───────────────────────────────────────────
function MapStats({ parcels }: { parcels: Parcel[] }) {
  const n = parcels.length;
  if (!n) return null;
  const totalHa = parcels.reduce((s, p) => s + p.area_ha, 0);
  const bins = [
    { label: "Very High", cnt: parcels.filter((p) => p.score >= 3.5).length,  color: "#0d8043" },
    { label: "High",      cnt: parcels.filter((p) => p.score >= 2.75 && p.score < 3.5).length, color: "#1a73e8" },
    { label: "Moderate",  cnt: parcels.filter((p) => p.score >= 2.0  && p.score < 2.75).length, color: "#e37400" },
    { label: "Low",       cnt: parcels.filter((p) => p.score < 2.0).length,   color: "#c5221f" },
  ];
  return (
    <div className="map-overlay map-stats" style={{ minWidth: 164 }}>
      <div className="overlay-label">{n.toLocaleString()} polygons shown</div>
      <div style={{ fontSize: 10, color: "hsl(var(--foreground-tertiary))", marginBottom: 8, fontFamily: "monospace" }}>
        {totalHa >= 1000
          ? `${(totalHa / 1000).toFixed(1)} k ha`
          : `${totalHa.toFixed(0)} ha`} total area
      </div>
      {bins.map(({ label, cnt, color }) => {
        const pct = ((cnt / n) * 100).toFixed(0);
        return (
          <div key={label} style={{ marginBottom: 5 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 2 }}>
              <span style={{ color: "hsl(var(--foreground))", fontWeight: 500 }}>{label}</span>
              <span style={{ color: "hsl(var(--foreground-secondary))", fontFamily: "monospace", fontSize: 10 }}>
                {cnt.toLocaleString()} ({pct}%)
              </span>
            </div>
            <div style={{ height: 3, borderRadius: 2, background: "hsl(var(--border))" }}>
              <div style={{ height: "100%", borderRadius: 2, width: `${pct}%`, background: color, transition: "width 0.4s" }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── Leaflet GeoJSON polygon tooltip content ──────────────────────────────────
function buildTooltipHTML(props: Record<string, any>): string {
  const score = props.score ?? 0;
  const sc = scoreLabel(score);
  const bc = badgeClass(score);
  const strokeColor = scoreStroke(score);
  return `
    <div style="font-family:'Inter',system-ui,sans-serif;min-width:220px;font-size:12px;padding:2px">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
        <span style="font-weight:700;font-size:13px;color:#202124">${props.id ?? ""}</span>
        <span class="badge-score ${bc}" style="font-size:10px">${sc}</span>
      </div>
      <div style="font-size:11px;color:#5f6368;margin-bottom:8px;font-weight:500">
        ${lulcIcon(props.lulc ?? "")} ${props.lulc ?? ""}
        &nbsp;·&nbsp; ${(props.area_ha ?? 0).toFixed(1)} ha
      </div>
      <table style="width:100%;border-collapse:collapse">
        <tbody>
          ${[
            ["Score",       `<strong style="color:${strokeColor}">${(score).toFixed(3)} / 4.00</strong>`],
            ["GHI",         `${(props.ghi ?? 0).toFixed(0)} kWh/m²/yr`],
            ["PV Yield",    `${(props.pv_yield ?? 0).toFixed(0)} kWh/kWp/yr`],
            ["Slope",       `${(props.slope ?? 0).toFixed(1)}°`],
            ["Elevation",   `${(props.elev ?? 0).toFixed(0)} m`],
            ["Temperature", `${(props.temp ?? 0).toFixed(1)} °C`],
            ["Grid Dist.",  `${(props.pwr_km ?? 0).toFixed(1)} km`],
            ["Road Dist.",  `${(props.road_km ?? 0).toFixed(1)} km`],
          ].map(([k, v]) => `
            <tr>
              <td style="color:#80868b;padding:2px 8px 2px 0;font-size:11px;white-space:nowrap">${k}</td>
              <td style="text-align:right;padding:2px 0;font-size:11px;font-family:monospace">${v}</td>
            </tr>`).join("")}
        </tbody>
      </table>
      <div style="margin-top:8px;font-size:10px;color:#bdc1c6;font-family:monospace">
        ${(props.lat ?? 0).toFixed(5)}°N &nbsp; ${(props.lon ?? 0).toFixed(5)}°E
      </div>
    </div>
  `;
}

// ─── GeoJSON layer with choropleth styling ────────────────────────────────────
function PolygonLayer({ geojson, key: geoKey }: { geojson: FeatureCollection; key: string }) {
  const map = useMap();
  const layerRef = useRef<L.GeoJSON | null>(null);

  useEffect(() => {
    if (layerRef.current) {
      layerRef.current.clearLayers();
      layerRef.current.addData(geojson);
    }
  }, [geojson]);

  function style(feature?: Feature): PathOptions {
    const s: number = (feature?.properties as any)?.score ?? 0;
    return {
      color:       scoreStroke(s),
      fillColor:   scoreFill(s),
      fillOpacity: 0.72,
      weight:      1.0,
      opacity:     0.9,
    };
  }

  function onEachFeature(feature: Feature, layer: Layer) {
    const props = feature.properties as Record<string, any>;
    const popup = L.popup({ maxWidth: 280, className: "parcel-popup" }).setContent(buildTooltipHTML(props));
    layer.bindPopup(popup);
    layer.on({
      mouseover: (e: LeafletMouseEvent) => {
        const l = e.target as L.Path;
        const s = props.score ?? 0;
        l.setStyle({ weight: 2.5, fillOpacity: 0.92, color: scoreStroke(s) });
        l.bringToFront();
        // show tooltip on hover
        popup.setLatLng(e.latlng).openOn(map);
      },
      mouseout: (e: LeafletMouseEvent) => {
        const l = e.target as L.Path;
        l.setStyle(style(feature));
        map.closePopup(popup);
      },
      click: (e: LeafletMouseEvent) => {
        const l = e.target as L.Path;
        popup.setLatLng(e.latlng).openOn(map);
      },
    });
  }

  return (
    <GeoJSON
      ref={layerRef as any}
      data={geojson}
      style={style}
      onEachFeature={onEachFeature}
      key={geoKey}
    />
  );
}

// ─── Main component ──────────────────────────────────────────────────────────
interface Props {
  parcels: Parcel[];
  weights: Weights;
  filters: Filters;
}

export function SuitabilityMap({ parcels, weights, filters }: Props) {
  const [basemap, setBasemap] = useState<string>("Light");
  const [geojson, setGeojson] = useState<FeatureCollection | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fetchUrlRef = useRef("");

  // Fetch GeoJSON from /api/geojson endpoint (polygon geometries)
  useEffect(() => {
    const url = buildGeoJSONUrl(weights, filters);
    if (url === fetchUrlRef.current) return;
    fetchUrlRef.current = url;
    setLoading(true);
    setError(null);
    apiRequest(url)
      .then((r) => r.json())
      .then((data) => {
        setGeojson(data as FeatureCollection);
        setLoading(false);
      })
      .catch((e) => {
        setError(String(e));
        setLoading(false);
      });
  }, [weights, filters]);

  const { url, attr } = BASEMAPS[basemap];
  const geojsonKey = geojson ? `gj-${geojson.features?.length}-${basemap}` : "empty";

  return (
    <div style={{
      flex: 1,
      margin: "0 24px 20px",
      position: "relative",
      borderRadius: "var(--radius-lg)",
      overflow: "hidden",
      border: "1px solid hsl(var(--border))",
      boxShadow: "var(--shadow-1)",
      minHeight: 400,
    }}>
      {/* Loading banner */}
      {loading && (
        <div style={{
          position: "absolute", top: 12, left: "50%", transform: "translateX(-50%)",
          zIndex: 1000, background: "rgba(32,33,36,0.88)", color: "#fff",
          fontSize: 11, fontWeight: 600, padding: "5px 12px", borderRadius: 20,
          display: "flex", alignItems: "center", gap: 6,
        }}>
          <span style={{ display: "inline-block", animation: "spin 1s linear infinite" }}>⟳</span>
          Loading polygons…
        </div>
      )}
      {/* Error banner */}
      {error && (
        <div style={{
          position: "absolute", top: 12, left: "50%", transform: "translateX(-50%)",
          zIndex: 1000, background: "#c5221f", color: "#fff",
          fontSize: 11, padding: "5px 12px", borderRadius: 20,
        }}>
          Map error: {error}
        </div>
      )}

      <MapContainer
        center={[11.85, 79.0]}
        zoom={9}
        style={{ width: "100%", height: "100%" }}
        scrollWheelZoom
        zoomControl
      >
        <TileLayer url={url} attribution={attr} key={basemap} />
        {geojson && <FitBounds geojson={geojson} />}
        {geojson && <PolygonLayer geojson={geojson} key={geojsonKey} />}
      </MapContainer>

      {/* Floating overlays */}
      <MapStats   parcels={parcels} />
      <BasemapSelector active={basemap} onChange={setBasemap} />
      <MapLegend />
    </div>
  );
}
