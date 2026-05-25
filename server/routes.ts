import type { Express } from "express";
import type { Server } from "http";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";

// Derive __dirname from import.meta.url (ESM-native).
// In dev (tsx), this resolves to the source server/ directory.
// In production (esbuild CJS bundle), the build script injects a
// __dirname banner shim so this import is never reached.
const __filename = fileURLToPath(import.meta.url);
const __dirname  = path.dirname(__filename);
const DATA_DIR   = __dirname;

// ── Types ────────────────────────────────────────────────────────────────────

interface FlatParcel {
  id: number;
  lulc: number;
  lulc_class: string;
  area_ha: number;
  lat: number;
  lon: number;
  elev: number;
  slope: number;
  ghi: number;
  pv_yield: number;
  temp: number;
  pwr_km: number;
  road_km: number;
  s_slope: number;
  s_ghi: number;
  s_power: number;
  s_road: number;
  s_temp: number;
  s_lulc: number;
  score: number;
  class: string;
}

interface GeoParcel {
  type: "Feature";
  geometry: {
    type: string;
    coordinates: unknown;
  };
  properties: FlatParcel;
}

interface GeoJSON {
  type: "FeatureCollection";
  features: GeoParcel[];
}

// ── Load data files at startup ───────────────────────────────────────────────

const flatPath = path.join(DATA_DIR, "barren_parcels_flat.json");
const geoPath  = path.join(DATA_DIR, "barren_parcels.geojson");

let FLAT_PARCELS: FlatParcel[] = [];
let GEO_DATA: GeoJSON = { type: "FeatureCollection", features: [] };

try {
  FLAT_PARCELS = JSON.parse(fs.readFileSync(flatPath, "utf8")) as FlatParcel[];
  console.log(`✅ Loaded ${FLAT_PARCELS.length} flat parcels from barren_parcels_flat.json`);
} catch (e) {
  console.error("❌ Could not load barren_parcels_flat.json:", e);
}

try {
  GEO_DATA = JSON.parse(fs.readFileSync(geoPath, "utf8")) as GeoJSON;
  console.log(`✅ Loaded ${GEO_DATA.features?.length ?? 0} GeoJSON features from barren_parcels.geojson`);
} catch (e) {
  console.error("❌ Could not load barren_parcels.geojson:", e);
}

// ── Suitability helpers ──────────────────────────────────────────────────────

function computeScore(p: FlatParcel, weights: Record<string, number>): number {
  const total = Object.values(weights).reduce((a, b) => a + b, 0) || 1;
  const w = Object.fromEntries(
    Object.entries(weights).map(([k, v]) => [k, v / total])
  );
  return (
    (w.slope ?? 0) * p.s_slope +
    (w.ghi   ?? 0) * p.s_ghi   +
    (w.power ?? 0) * p.s_power +
    (w.road  ?? 0) * p.s_road  +
    (w.temp  ?? 0) * p.s_temp  +
    (w.lulc  ?? 0) * p.s_lulc
  );
}

function suitClass(score: number): string {
  if (score >= 3.5)  return "Very High";
  if (score >= 2.75) return "High";
  if (score >= 2.0)  return "Moderate";
  return "Low";
}

function parseNum(val: unknown, def: number): number {
  const n = parseFloat(val as string);
  return isNaN(n) ? def : n;
}

// ── Route registration ───────────────────────────────────────────────────────

export async function registerRoutes(httpServer: Server, app: Express): Promise<Server> {

  // ── GET /api/parcels ────────────────────────────────────────────────────────
  // Returns flat JSON array with re-computed scores + class based on user weights
  app.get("/api/parcels", (req, res) => {
    const weights = {
      slope: parseNum(req.query.w_slope, 5),
      ghi:   parseNum(req.query.w_ghi,   5),
      power: parseNum(req.query.w_power, 5),
      road:  parseNum(req.query.w_road,  5),
      temp:  parseNum(req.query.w_temp,  5),
      lulc:  parseNum(req.query.w_lulc,  5),
    };

    const lulcFilter    = req.query.lulc       as string | undefined;
    const classFilter   = req.query.suit_class as string | undefined;
    const maxSlope      = parseNum(req.query.max_slope,      999);
    const maxPowerDist  = parseNum(req.query.max_power_dist, 999);
    const minArea       = parseNum(req.query.min_area,       0);

    const result = FLAT_PARCELS
      .filter((p) => {
        if (lulcFilter  && lulcFilter  !== "all" && p.lulc_class !== lulcFilter)  return false;
        if (p.slope     > maxSlope)      return false;
        if (p.pwr_km    > maxPowerDist)  return false;
        if (p.area_ha   < minArea)       return false;
        return true;
      })
      .map((p) => {
        const score = computeScore(p, weights);
        const cls   = suitClass(score);
        if (classFilter && classFilter !== "all" && cls !== classFilter) return null;
        return {
          ...p,
          score: Math.round(score * 1000) / 1000,
          class: cls,
        };
      })
      .filter(Boolean);

    res.json(result);
  });

  // ── GET /api/geojson ────────────────────────────────────────────────────────
  // Returns GeoJSON FeatureCollection with same filters + re-computed scores
  app.get("/api/geojson", (req, res) => {
    const weights = {
      slope: parseNum(req.query.w_slope, 5),
      ghi:   parseNum(req.query.w_ghi,   5),
      power: parseNum(req.query.w_power, 5),
      road:  parseNum(req.query.w_road,  5),
      temp:  parseNum(req.query.w_temp,  5),
      lulc:  parseNum(req.query.w_lulc,  5),
    };

    const lulcFilter   = req.query.lulc       as string | undefined;
    const classFilter  = req.query.suit_class as string | undefined;
    const maxSlope     = parseNum(req.query.max_slope,      999);
    const maxPowerDist = parseNum(req.query.max_power_dist, 999);
    const minArea      = parseNum(req.query.min_area,       0);

    const features = GEO_DATA.features
      .filter((f) => {
        const p = f.properties;
        if (lulcFilter && lulcFilter !== "all" && p.lulc_class !== lulcFilter)  return false;
        if (p.slope    > maxSlope)      return false;
        if (p.pwr_km   > maxPowerDist)  return false;
        if (p.area_ha  < minArea)       return false;
        return true;
      })
      .map((f) => {
        const score = computeScore(f.properties, weights);
        const cls   = suitClass(score);
        if (classFilter && classFilter !== "all" && cls !== classFilter) return null;
        return {
          ...f,
          properties: {
            ...f.properties,
            score: Math.round(score * 1000) / 1000,
            class: cls,
          },
        };
      })
      .filter(Boolean);

    res.json({
      type: "FeatureCollection",
      features,
    });
  });

  // ── GET /api/meta ───────────────────────────────────────────────────────────
  app.get("/api/meta", (_req, res) => {
    const lulcTypes   = [...new Set(FLAT_PARCELS.map((p) => p.lulc_class))].sort();
    const suitClasses = [...new Set(FLAT_PARCELS.map((p) => p.class))].sort();

    const lats = FLAT_PARCELS.map((p) => p.lat);
    const lons = FLAT_PARCELS.map((p) => p.lon);

    res.json({
      total_parcels: FLAT_PARCELS.length,
      total_area_ha: Math.round(FLAT_PARCELS.reduce((s, p) => s + p.area_ha, 0)),
      lulc_types:    lulcTypes,
      suit_classes:  suitClasses,
      bbox: {
        min_lat: Math.min(...lats),
        max_lat: Math.max(...lats),
        min_lon: Math.min(...lons),
        max_lon: Math.max(...lons),
      },
      data_sources: {
        lulc:          "ESA WorldCover 2021 v200",
        elevation:     "NASA SRTM 30m",
        slope:         "Derived from SRTM DEM",
        solar_ghi:     "PVGIS 5.2 / ERA5",
        climate:       "NASA POWER v8 MERRA-2",
        power_grid:    "OpenStreetMap Overpass API",
        roads_highways:"OpenStreetMap Overpass API",
      },
    });
  });

  return httpServer;
}
