import type { Express } from "express";
import type { Server } from "http";
import parcelsRaw from "./parcels.json";

interface Parcel {
  parcel_id: string;
  village: string;
  lat: number;
  lon: number;
  elevation_m: number;
  slope_deg: number;
  slope_score: number;
  lulc_class: number;
  lulc_name: string;
  lulc_score: number;
  ghi_kwh_m2_yr: number;
  pv_yield_kwh_kwp: number;
  ghi_score: number;
  ghi_daily: number;
  temp_c: number;
  temp_score: number;
  power_dist_km: number;
  power_score: number;
  road_dist_km: number;
  road_score: number;
  suitability_score?: number;
  suitability_class?: string;
  sources?: Record<string, string>;
}

const PARCELS: Parcel[] = parcelsRaw as Parcel[];

function computeSuitability(
  p: Parcel,
  weights: Record<string, number>
): number {
  const total = Object.values(weights).reduce((a, b) => a + b, 0) || 1;
  const nw = Object.fromEntries(
    Object.entries(weights).map(([k, v]) => [k, v / total])
  );
  return (
    (nw.slope  ?? 0) * p.slope_score  +
    (nw.lulc   ?? 0) * p.lulc_score   +
    (nw.ghi    ?? 0) * p.ghi_score    +
    (nw.power  ?? 0) * p.power_score  +
    (nw.road   ?? 0) * p.road_score   +
    (nw.temp   ?? 0) * p.temp_score
  );
}

function suitabilityClass(score: number): string {
  if (score >= 3.25) return "Very High";
  if (score >= 2.5)  return "High";
  if (score >= 1.75) return "Moderate";
  return "Low";
}

export async function registerRoutes(httpServer: Server, app: Express): Promise<Server> {
  // GET /api/parcels — return all parcels with computed suitability
  app.get("/api/parcels", (req, res) => {
    const weights = {
      slope: parseFloat(req.query.w_slope as string ?? "3"),
      lulc:  parseFloat(req.query.w_lulc  as string ?? "3"),
      ghi:   parseFloat(req.query.w_ghi   as string ?? "3"),
      power: parseFloat(req.query.w_power as string ?? "2"),
      road:  parseFloat(req.query.w_road  as string ?? "1"),
      temp:  parseFloat(req.query.w_temp  as string ?? "1"),
    };

    // Optional filters
    const village      = req.query.village as string | undefined;
    const lulcFilter   = req.query.lulc_name as string | undefined;
    const maxSlope     = parseFloat(req.query.max_slope as string ?? "999");
    const maxPowerDist = parseFloat(req.query.max_power_dist as string ?? "999");

    let parcels = PARCELS.filter((p) => {
      if (village && village.toLowerCase() !== "all" && p.village !== village) return false;
      if (lulcFilter && lulcFilter.toLowerCase() !== "all" && p.lulc_name !== lulcFilter) return false;
      if (p.slope_deg > maxSlope) return false;
      if (p.power_dist_km > maxPowerDist) return false;
      return true;
    });

    const result = parcels.map((p) => {
      const score = computeSuitability(p, weights);
      return {
        ...p,
        suitability_score: Math.round(score * 1000) / 1000,
        suitability_class: suitabilityClass(score),
        sources: undefined,  // strip verbose field
      };
    });

    res.json(result);
  });

  // GET /api/meta — district summary, village list, lulc list
  app.get("/api/meta", (_req, res) => {
    const villages  = [...new Set(PARCELS.map((p) => p.village))].sort();
    const lulcNames = [...new Set(PARCELS.map((p) => p.lulc_name))].sort();
    res.json({
      total_parcels: PARCELS.length,
      villages,
      lulc_names: lulcNames,
      bbox: {
        min_lat: Math.min(...PARCELS.map((p) => p.lat)),
        max_lat: Math.max(...PARCELS.map((p) => p.lat)),
        min_lon: Math.min(...PARCELS.map((p) => p.lon)),
        max_lon: Math.max(...PARCELS.map((p) => p.lon)),
      },
      data_sources: {
        lulc:      "ESA WorldCover 2020 v100",
        elevation: "NASA SRTM30m",
        solar:     "PVGIS API v5.2 ERA5",
        climate:   "NASA POWER v8 MERRA-2",
        grid:      "OpenStreetMap Overpass API",
        roads:     "OpenStreetMap Overpass API",
      },
    });
  });

  return httpServer;
}
