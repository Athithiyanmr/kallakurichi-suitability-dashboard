import type { Express } from "express";
import type { Server } from "http";
import * as fs from "fs";
import * as path from "path";

// ─── Parcel schema (flat properties from barren_parcels_flat.json) ────────────
interface Parcel {
  id:         string;
  lulc:       string;
  lulc_class: number;
  area_ha:    number;
  lat:        number;
  lon:        number;
  elev:       number;
  slope:      number;
  ghi:        number;
  pv_yield:   number;
  temp:       number;
  pwr_km:     number;
  road_km:    number;
  s_slope:    number;
  s_ghi:      number;
  s_power:    number;
  s_road:     number;
  s_temp:     number;
  s_lulc:     number;
  score:      number;
  class:      string;
}

// ─── Load data once at startup ────────────────────────────────────────────────
const dataDir = path.join(__dirname);

let PARCELS: Parcel[] = [];
let GEOJSON_STR: string = "";

try {
  const flatPath = path.join(dataDir, "barren_parcels_flat.json");
  PARCELS = JSON.parse(fs.readFileSync(flatPath, "utf8")) as Parcel[];
  console.log(`[routes] Loaded ${PARCELS.length} barren parcels`);
} catch (e) {
  console.warn("[routes] barren_parcels_flat.json not found, using empty dataset");
}

try {
  const gjPath = path.join(dataDir, "barren_parcels.geojson");
  GEOJSON_STR = fs.readFileSync(gjPath, "utf8");
  console.log(`[routes] GeoJSON loaded (${(GEOJSON_STR.length / 1024 / 1024).toFixed(1)} MB)`);
} catch (e) {
  console.warn("[routes] barren_parcels.geojson not found");
  GEOJSON_STR = '{"type":"FeatureCollection","features":[]}';
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function computeScore(p: Parcel, weights: Record<string, number>): number {
  const total = Object.values(weights).reduce((a, b) => a + b, 0) || 1;
  const nw    = Object.fromEntries(Object.entries(weights).map(([k, v]) => [k, v / total]));
  return (
    (nw.slope ?? 0) * p.s_slope +
    (nw.lulc  ?? 0) * p.s_lulc  +
    (nw.ghi   ?? 0) * p.s_ghi   +
    (nw.power ?? 0) * p.s_power +
    (nw.road  ?? 0) * p.s_road  +
    (nw.temp  ?? 0) * p.s_temp
  );
}

function suitClass(score: number): string {
  if (score >= 3.5)  return "Very High";
  if (score >= 2.75) return "High";
  if (score >= 2.0)  return "Moderate";
  return "Low";
}

// ─── Routes ───────────────────────────────────────────────────────────────────
export async function registerRoutes(httpServer: Server, app: Express): Promise<Server> {

  // ── GET /api/parcels — flat list with re-scored suitability ─────────────────
  app.get("/api/parcels", (req, res) => {
    const weights = {
      slope: parseFloat((req.query.w_slope as string) ?? "5"),
      lulc:  parseFloat((req.query.w_lulc  as string) ?? "5"),
      ghi:   parseFloat((req.query.w_ghi   as string) ?? "5"),
      power: parseFloat((req.query.w_power as string) ?? "5"),
      road:  parseFloat((req.query.w_road  as string) ?? "5"),
      temp:  parseFloat((req.query.w_temp  as string) ?? "5"),
    };

    const lulcFilter   = (req.query.lulc    as string | undefined)?.toLowerCase();
    const maxSlope     = parseFloat((req.query.max_slope     as string) ?? "999");
    const maxPowerDist = parseFloat((req.query.max_power_dist as string) ?? "999");
    const minArea      = parseFloat((req.query.min_area      as string) ?? "0");
    const suitFilter   = (req.query.suit_class as string | undefined)?.toLowerCase();

    const result = PARCELS
      .filter((p) => {
        if (lulcFilter && lulcFilter !== "all" && p.lulc.toLowerCase() !== lulcFilter) return false;
        if (p.slope    > maxSlope)     return false;
        if (p.pwr_km   > maxPowerDist) return false;
        if (p.area_ha  < minArea)      return false;
        return true;
      })
      .map((p) => {
        const score = Math.round(computeScore(p, weights) * 1000) / 1000;
        const cls   = suitClass(score);
        return { ...p, score, class: cls };
      })
      .filter((p) => {
        if (suitFilter && suitFilter !== "all" && p.class.toLowerCase() !== suitFilter) return false;
        return true;
      })
      .sort((a, b) => b.score - a.score);

    res.json(result);
  });

  // ── GET /api/geojson — full polygon GeoJSON with re-scored suitability ──────
  // Serve the GeoJSON with updated scores based on weight params
  // For performance, if no custom weights: serve raw cached string
  app.get("/api/geojson", (req, res) => {
    const hasWeights = Object.keys(req.query).some((k) => k.startsWith("w_"));

    if (!hasWeights) {
      // Serve pre-built file directly (fast path)
      res.setHeader("Content-Type", "application/geo+json");
      res.setHeader("Cache-Control", "public, max-age=60");
      res.send(GEOJSON_STR);
      return;
    }

    // Re-score with custom weights
    const weights = {
      slope: parseFloat((req.query.w_slope as string) ?? "5"),
      lulc:  parseFloat((req.query.w_lulc  as string) ?? "5"),
      ghi:   parseFloat((req.query.w_ghi   as string) ?? "5"),
      power: parseFloat((req.query.w_power as string) ?? "5"),
      road:  parseFloat((req.query.w_road  as string) ?? "5"),
      temp:  parseFloat((req.query.w_temp  as string) ?? "5"),
    };

    const lulcFilter   = (req.query.lulc    as string | undefined)?.toLowerCase();
    const maxSlope     = parseFloat((req.query.max_slope as string) ?? "999");
    const maxPowerDist = parseFloat((req.query.max_power_dist as string) ?? "999");
    const minArea      = parseFloat((req.query.min_area as string) ?? "0");

    // Parse base GeoJSON and re-score features
    const base = JSON.parse(GEOJSON_STR);
    const features = base.features
      .filter((f: any) => {
        const p = f.properties;
        if (lulcFilter && lulcFilter !== "all" && p.lulc?.toLowerCase() !== lulcFilter) return false;
        if (p.slope   > maxSlope)     return false;
        if (p.pwr_km  > maxPowerDist) return false;
        if (p.area_ha < minArea)      return false;
        return true;
      })
      .map((f: any) => {
        // Build a Parcel-like object from GeoJSON properties
        const p = f.properties as Parcel;
        const score = Math.round(computeScore(p, weights) * 1000) / 1000;
        return {
          ...f,
          properties: { ...p, score, class: suitClass(score) },
        };
      });

    res.setHeader("Content-Type", "application/geo+json");
    res.json({ ...base, features });
  });

  // ── GET /api/meta ────────────────────────────────────────────────────────────
  app.get("/api/meta", (_req, res) => {
    const lulcTypes = [...new Set(PARCELS.map((p) => p.lulc))].sort();
    const suitCls   = [...new Set(PARCELS.map((p) => p.class))];
    const totalHa   = PARCELS.reduce((s, p) => s + p.area_ha, 0);

    res.json({
      total_parcels:  PARCELS.length,
      total_area_ha:  Math.round(totalHa),
      lulc_types:     lulcTypes,
      suit_classes:   ["Very High", "High", "Moderate", "Low"],
      bbox: {
        min_lat: Math.min(...PARCELS.map((p) => p.lat)),
        max_lat: Math.max(...PARCELS.map((p) => p.lat)),
        min_lon: Math.min(...PARCELS.map((p) => p.lon)),
        max_lon: Math.max(...PARCELS.map((p) => p.lon)),
      },
      data_sources: {
        lulc:      "ESA WorldCover 2021 v200 (10 m)",
        elevation: "NASA SRTM 30 m via OpenTopoData",
        solar:     "PVGIS API v5.2 ERA5",
        climate:   "NASA POWER v8 MERRA-2",
        grid:      "OpenStreetMap Overpass API",
        roads:     "OpenStreetMap Overpass API",
      },
    });
  });

  return httpServer;
}
