"""
06_filter_solar_candidates.py — Post-Process Barren Land Solar Candidates
=========================================================================
Reads the patch-level barren land analysis produced by script 07
(data/processed/barren_analysis.json) and applies configurable filters
to identify the top solar development candidates.

This script requires script 07 to have been run first.

Filters applied (all configurable below):
  - Minimum patch area            (MIN_AREA_HA)
  - Maximum terrain slope         (MAX_SLOPE_DEG)
  - Minimum annual GHI            (MIN_GHI_KWH_M2_YR)
  - Maximum distance to substation (MAX_POWER_DIST_KM)
  - Maximum distance to highway   (MAX_ROAD_DIST_KM)

Scoring:
  Each passing patch receives a composite suitability score 1–4 using the
  same per-factor thresholds defined in config.py.

Outputs:
  data/processed/solar_candidates.csv     — ranked candidate table
  data/processed/solar_candidates.geojson — GeoJSON for QGIS / Leaflet

Usage: python scripts/06_filter_solar_candidates.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import PROC_DIR
from utils import (
    composite_score,
    get_logger,
    load_json,
    save_json,
    score_ghi,
    score_power,
    score_road,
    score_slope,
    score_temp,
    suitability_class,
)

log = get_logger("06_filter")

# ─── Filter thresholds (edit to tighten / loosen criteria) ───────────────────────
MIN_AREA_HA       = 1.0      # ha — minimum patch size
MAX_SLOPE_DEG     = 15.0     # ° — maximum allowable slope
MIN_GHI_KWH_M2_YR = 1900.0  # kWh/m²/yr — minimum annual GHI
MAX_POWER_DIST_KM = 15.0     # km — maximum distance to substation/power line
MAX_ROAD_DIST_KM  = 10.0     # km — maximum distance to primary/secondary road

# Composite score weights (equal by default)
WEIGHTS = {
    "slope": 1.0,
    "ghi":   1.0,
    "power": 1.0,
    "road":  1.0,
    "temp":  1.0,
}


# ─── Main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=" * 60)
    log.info("  Script 06 — Solar Candidate Filter")
    log.info("  (reads output of script 07: barren_analysis.json)")
    log.info("=" * 60)

    # ── Load barren analysis output ────────────────────────────────────────────
    analysis_path = PROC_DIR / "barren_analysis.json"
    if not analysis_path.exists():
        log.error(
            f"barren_analysis.json not found at {analysis_path}.\n"
            "Run script 07 first: python scripts/07_lulc_barren_analysis.py"
        )
        sys.exit(1)

    analysis = load_json(analysis_path)
    patches  = analysis.get("top_patches", [])
    if not patches:
        log.error("No patches found in barren_analysis.json.  Run script 07 first.")
        sys.exit(1)

    log.info(f"Input: {len(patches)} patches from barren_analysis.json")

    # ── Apply filters ──────────────────────────────────────────────────────────
    log.info("Applying filters:")
    log.info(f"  Min area       : {MIN_AREA_HA} ha")
    log.info(f"  Max slope      : {MAX_SLOPE_DEG}°")
    log.info(f"  Min GHI        : {MIN_GHI_KWH_M2_YR} kWh/m²/yr")
    log.info(f"  Max power dist : {MAX_POWER_DIST_KM} km")
    log.info(f"  Max road dist  : {MAX_ROAD_DIST_KM} km")

    candidates = [
        p for p in patches
        if (
            p.get("area_ha",       0)   >= MIN_AREA_HA
            and p.get("slope_deg", 99)  <= MAX_SLOPE_DEG
            and p.get("ghi_kwh_m2_yr", 0) >= MIN_GHI_KWH_M2_YR
            and p.get("power_dist_km", 99) <= MAX_POWER_DIST_KM
            and p.get("road_dist_km", 99)  <= MAX_ROAD_DIST_KM
        )
    ]
    log.info(f"Candidates passing all filters: {len(candidates)} / {len(patches)}")

    if not candidates:
        log.warning(
            "No candidates passed the filters.  "
            "Try relaxing MAX_POWER_DIST_KM or MIN_GHI_KWH_M2_YR thresholds."
        )
        sys.exit(0)

    # ── Score each candidate ───────────────────────────────────────────────────
    results = []
    for idx, p in enumerate(candidates, 1):
        scores = {
            "slope": score_slope(p.get("slope_deg",     0)),
            "ghi":   score_ghi(  p.get("ghi_kwh_m2_yr", 0)),
            "power": score_power(p.get("power_dist_km", 99)),
            "road":  score_road( p.get("road_dist_km",  99)),
            "temp":  score_temp( p.get("temp_c",         26)),
        }
        comp = composite_score(scores, WEIGHTS)
        suit = suitability_class(comp)

        results.append({
            "candidate_id":       f"SC-{idx:04d}",
            "patch_id":           p.get("patch_id"),
            "lat":                p["lat"],
            "lon":                p["lon"],
            "area_ha":            p.get("area_ha"),
            "area_km2":           p.get("area_km2"),
            "elevation_m":        p.get("elevation_m"),
            "slope_deg":          p.get("slope_deg"),
            "slope_score":        scores["slope"],
            "ghi_kwh_m2_yr":      p.get("ghi_kwh_m2_yr"),
            "pv_yield_kwh_kwp":   p.get("pv_yield_kwh_kwp"),
            "ghi_score":          scores["ghi"],
            "temp_c":             p.get("temp_c"),
            "temp_score":         scores["temp"],
            "power_dist_km":      p.get("power_dist_km"),
            "power_score":        scores["power"],
            "road_dist_km":       p.get("road_dist_km"),
            "road_score":         scores["road"],
            "suitability_score":  round(comp, 3),
            "suitability_class":  suit,
        })

    # Sort by composite score (descending)
    results.sort(key=lambda x: -x["suitability_score"])

    # ── Summary ────────────────────────────────────────────────────────────────
    log.info("-" * 60)
    total_ha = sum(r["area_ha"] for r in results)
    log.info(f"Candidates         : {len(results)}")
    log.info(f"Total candidate area: {total_ha:,.1f} ha  ({total_ha/100:.2f} km²)")
    for label in ("Very High", "High", "Moderate", "Low"):
        n = sum(1 for r in results if r["suitability_class"] == label)
        log.info(f"  {label:<10s}: {n}")

    log.info("\nTop 5 candidates:")
    for r in results[:5]:
        log.info(
            f"  {r['candidate_id']}  "
            f"lat={r['lat']:.5f} lon={r['lon']:.5f}  "
            f"area={r['area_ha']:.1f} ha  "
            f"score={r['suitability_score']:.3f}  ({r['suitability_class']})  "
            f"GHI={r['ghi_kwh_m2_yr']:.0f} kWh/m²/yr  "
            f"slope={r['slope_deg']:.1f}°  "
            f"power={r['power_dist_km']:.1f} km  road={r['road_dist_km']:.1f} km"
        )

    # ── Export CSV ─────────────────────────────────────────────────────────────
    import csv
    csv_path = PROC_DIR / "solar_candidates.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    log.info(f"\nSaved → {csv_path}")

    # ── Export GeoJSON ─────────────────────────────────────────────────────────
    geojson = {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
        },
        "metadata": {
            "title":              "Kallakurichi Solar Development Candidates",
            "lulc_source":        "ESA WorldCover 2021 v200 (class 60 — Bare/sparse veg)",
            "filters": {
                "min_area_ha":        MIN_AREA_HA,
                "max_slope_deg":      MAX_SLOPE_DEG,
                "min_ghi_kwh_m2_yr":  MIN_GHI_KWH_M2_YR,
                "max_power_dist_km":  MAX_POWER_DIST_KM,
                "max_road_dist_km":   MAX_ROAD_DIST_KM,
            },
            "n_candidates":       len(results),
            "total_area_ha":      round(total_ha, 2),
            "data_sources": [
                "ESA WorldCover 2021 v200 (AWS S3 public)",
                "NASA SRTM 30 m via OpenTopoData.org",
                "PVGIS API v5.2 ERA5",
                "NASA POWER v8 MERRA-2",
                "OpenStreetMap Overpass API",
            ],
        },
        "features": [
            {
                "type":     "Feature",
                "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
                "properties": {k: v for k, v in r.items() if k not in ("lat", "lon")},
            }
            for r in results
        ],
    }
    geojson_path = PROC_DIR / "solar_candidates.geojson"
    save_json(geojson, geojson_path)
    log.info(f"Saved → {geojson_path}")


if __name__ == "__main__":
    main()
