"""
05_process_data.py — Data Processing Pipeline
=============================================
Combines all raw data sources into a unified parcel-level analysis dataset.

Processing steps:
  1. Load raw JSON files (SRTM, PVGIS, NASA POWER, ESA LULC, OSM)
  2. Build 20×20 analysis grid over Kallakurichi district
  3. KD-tree nearest-neighbour interpolation for each factor layer
  4. Compute terrain slope from SRTM elevations (finite differences)
  5. Distance-to-feature calculations (power lines, roads) via KD-tree
  6. Score each factor 1–4 using thresholds from config.py
  7. Compute composite suitability score + classify
  8. Assign village zone labels

Outputs:
  data/processed/kallakurichi_parcels.json  — full records with all fields
  data/processed/kallakurichi_parcels.csv   — tabular version for GIS/BI tools

Output fields per parcel:
  parcel_id, village, lat, lon
  elevation_m, slope_deg, slope_score
  lulc_class, lulc_name, lulc_score
  ghi_kwh_m2_yr, pv_yield_kwh_kwp, ghi_score
  ghi_daily, temp_c, temp_score
  power_dist_km, power_score, road_dist_km, road_score
  suitability_score, suitability_class, sources

Usage: python scripts/05_process_data.py
"""

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    CITATIONS,
    GRID_N_LAT,
    GRID_N_LON,
    LULC_CLASSES,
    PROC_DIR,
    RAW_DIR,
    SRTM_LAT_MAX,
    SRTM_LAT_MIN,
    SRTM_LON_MAX,
    SRTM_LON_MIN,
    SOLAR_LAT_MAX,
    SOLAR_LAT_MIN,
    SOLAR_LON_MAX,
    SOLAR_LON_MIN,
)
from utils import (
    build_osm_kdtree,
    composite_score,
    get_logger,
    get_village,
    load_json,
    nn_interp,
    save_json,
    score_ghi,
    score_lulc,
    score_power,
    score_road,
    score_slope,
    score_temp,
    suitability_class,
)

log = get_logger("05_process")

# Default composite weights — equal across all six factors
WEIGHTS = {
    "slope": 1.0,
    "lulc":  1.0,
    "ghi":   1.0,
    "power": 1.0,
    "road":  1.0,
    "temp":  1.0,
}

# Analysis grid bounds (slightly tighter than district bbox to avoid edge effects)
GRID_LAT_MIN = SRTM_LAT_MIN
GRID_LAT_MAX = SRTM_LAT_MAX
GRID_LON_MIN = SRTM_LON_MIN
GRID_LON_MAX = SRTM_LON_MAX


# ─── Helpers ────────────────────────────────────────────────────────────────────

def compute_slope(elev_flat: np.ndarray, lat_g: np.ndarray,
                  lon_g: np.ndarray) -> np.ndarray:
    """
    Approximate terrain slope in degrees from a gridded elevation array.
    Uses central finite differences; edge pixels use one-sided differences.
    """
    eg      = elev_flat.reshape(len(lat_g), len(lon_g))
    lat_sp  = (lat_g[1] - lat_g[0]) * 111_320          # metres per row step
    lon_sp  = (lon_g[1] - lon_g[0]) * 111_320 * np.cos(np.radians(lat_g.mean()))
    dz_dy   = np.gradient(eg, axis=0) / lat_sp          # N–S gradient
    dz_dx   = np.gradient(eg, axis=1) / lon_sp          # E–W gradient
    return np.degrees(np.arctan(np.sqrt(dz_dx ** 2 + dz_dy ** 2))).ravel()


# ─── Main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=" * 60)
    log.info("  Script 05 — Data Processing Pipeline")
    log.info(f"  Grid: {GRID_N_LAT} × {GRID_N_LON} = {GRID_N_LAT * GRID_N_LON} parcels")
    log.info("=" * 60)

    # ── 1. Load raw data ────────────────────────────────────────────────────────
    log.info("[1/7] Loading raw data files...")

    elev_raw = load_json(RAW_DIR / "srtm_elevation.json")["points"]
    ghi_raw  = load_json(RAW_DIR / "pvgis_ghi.json")["points"]
    nasa_raw = load_json(RAW_DIR / "nasa_power_ghi.json")["points"]
    lulc_raw = load_json(RAW_DIR / "esa_worldcover_lulc.json")["points"]
    pwr_osm  = load_json(RAW_DIR / "osm_power.json")
    hwy_osm  = load_json(RAW_DIR / "osm_highways.json")

    log.info(
        f"  SRTM: {len(elev_raw)} pts | PVGIS: {len(ghi_raw)} pts | "
        f"NASA: {len(nasa_raw)} pts | LULC: {len(lulc_raw)} pts | "
        f"Power elements: {len(pwr_osm.get('elements', []))} | "
        f"Highway elements: {len(hwy_osm.get('elements', []))}"
    )

    # ── 2. Build analysis grid ─────────────────────────────────────────────────
    log.info("[2/7] Building analysis grid...")
    lat_g = np.linspace(GRID_LAT_MIN, GRID_LAT_MAX, GRID_N_LAT)
    lon_g = np.linspace(GRID_LON_MIN, GRID_LON_MAX, GRID_N_LON)
    lons_2d, lats_2d = np.meshgrid(lon_g, lat_g)
    grid_pts = np.column_stack([lats_2d.ravel(), lons_2d.ravel()])
    log.info(f"  {len(grid_pts)} grid points ({GRID_N_LAT}×{GRID_N_LON})")

    # ── 3. SRTM elevation + slope ──────────────────────────────────────────────
    log.info("[3/7] Interpolating elevation and computing slope...")
    elev_pts  = np.array([[p["lat"], p["lon"]] for p in elev_raw])
    elev_vals = np.array([p["elevation_m"] for p in elev_raw])
    grid_elev, _ = nn_interp(elev_pts, elev_vals, grid_pts)
    grid_slope   = compute_slope(grid_elev, lat_g, lon_g)

    log.info(
        f"  Elevation: {grid_elev.min():.0f}–{grid_elev.max():.0f} m | "
        f"Slope: {grid_slope.min():.1f}–{grid_slope.max():.1f}°"
    )

    # ── 4. ESA WorldCover LULC ────────────────────────────────────────────────
    log.info("[4/7] Interpolating LULC...")
    lulc_pts       = np.array([[p["lat"], p["lon"]] for p in lulc_raw])
    lulc_cls_vals  = np.array([p["lulc_class"] for p in lulc_raw])
    lulc_name_vals = np.array([p["lulc_name"]  for p in lulc_raw])

    grid_lulc_cls,  _ = nn_interp(lulc_pts, lulc_cls_vals,                   grid_pts)
    grid_lulc_idx,  _ = nn_interp(lulc_pts, np.arange(len(lulc_name_vals)),  grid_pts)
    grid_lulc_name    = lulc_name_vals[grid_lulc_idx]

    unique_classes, counts = np.unique(grid_lulc_cls, return_counts=True)
    log.info("  LULC class distribution:")
    for cls, cnt in zip(unique_classes, counts):
        name = LULC_CLASSES.get(int(cls), ("Unknown",))[0]
        log.info(f"    {int(cls):>3}  {name:<25s} {int(cnt):>4} px")

    # ── 5. PVGIS GHI + PV yield ────────────────────────────────────────────────
    log.info("[5/7] Interpolating solar radiation...")
    ghi_pts  = np.array([[p["lat"], p["lon"]] for p in ghi_raw])
    ghi_vals = np.array([p.get("ghi_kwh_m2_yr") or 0.0 for p in ghi_raw])
    ey_vals  = np.array([p.get("pv_yield_kwh_kwp") or p.get("E_y") or 0.0 for p in ghi_raw])

    grid_ghi, _ = nn_interp(ghi_pts, ghi_vals, grid_pts)
    grid_ey,  _ = nn_interp(ghi_pts, ey_vals,  grid_pts)

    log.info(f"  GHI: {grid_ghi.min():.0f}–{grid_ghi.max():.0f} kWh/m²/yr")

    # ── 6. NASA POWER (temperature + daily GHI) ────────────────────────────────
    nasa_pts   = np.array([[p["lat"], p["lon"]] for p in nasa_raw])
    nasa_ghi_d = np.array([p.get("GHI_kwh_m2_day") or 0.0 for p in nasa_raw])
    nasa_t2m   = np.array([p.get("temp_c")          or 0.0 for p in nasa_raw])

    grid_ghi_daily, _ = nn_interp(nasa_pts, nasa_ghi_d, grid_pts)
    grid_temp,      _ = nn_interp(nasa_pts, nasa_t2m,   grid_pts)
    log.info(f"  Temperature: {grid_temp.min():.1f}–{grid_temp.max():.1f} °C")

    # ── 7. OSM distances via KD-tree ───────────────────────────────────────────
    log.info("[7/7] Computing OSM distances...")

    pwr_tree = build_osm_kdtree(pwr_osm)
    hwy_tree = build_osm_kdtree(hwy_osm)

    if pwr_tree is not None:
        pwr_dists_deg = pwr_tree.query(grid_pts)[0]
        pwr_dists_km  = pwr_dists_deg * 111.0
    else:
        log.warning("  No power-line nodes found — defaulting to 50 km")
        pwr_dists_km = np.full(len(grid_pts), 50.0)

    if hwy_tree is not None:
        hwy_dists_deg = hwy_tree.query(grid_pts)[0]
        hwy_dists_km  = hwy_dists_deg * 111.0
    else:
        log.warning("  No highway nodes found — defaulting to 30 km")
        hwy_dists_km = np.full(len(grid_pts), 30.0)

    log.info(
        f"  Power dist: {pwr_dists_km.min():.2f}–{pwr_dists_km.max():.2f} km | "
        f"Road dist: {hwy_dists_km.min():.2f}–{hwy_dists_km.max():.2f} km"
    )

    # ── Assemble records ───────────────────────────────────────────────────────
    log.info("Assembling parcel records and computing suitability scores...")
    source_meta = {
        "elevation": CITATIONS["srtm"],
        "solar":     CITATIONS["pvgis"],
        "nasa":      CITATIONS["nasa_power"],
        "lulc":      CITATIONS["esa_worldcover"],
        "power":     CITATIONS["osm"],
        "roads":     CITATIONS["osm"],
    }

    records: list[dict] = []
    for i in range(len(grid_pts)):
        lat, lon = float(grid_pts[i, 0]), float(grid_pts[i, 1])

        s_slope = score_slope(float(grid_slope[i]))
        s_lulc  = score_lulc(int(grid_lulc_cls[i]))
        s_ghi   = score_ghi(float(grid_ghi[i]))
        s_power = score_power(float(pwr_dists_km[i]))
        s_road  = score_road(float(hwy_dists_km[i]))
        s_temp  = score_temp(float(grid_temp[i]))

        scores = {
            "slope": s_slope, "lulc": s_lulc, "ghi": s_ghi,
            "power": s_power, "road": s_road,  "temp": s_temp,
        }
        comp = composite_score(scores, WEIGHTS)
        suit = suitability_class(comp)

        records.append({
            "parcel_id":          f"KLK-{i + 1:04d}",
            "village":            get_village(lat, lon),
            "lat":                round(lat, 5),
            "lon":                round(lon, 5),
            "elevation_m":        round(float(grid_elev[i]),   1),
            "slope_deg":          round(float(grid_slope[i]),  2),
            "slope_score":        s_slope,
            "lulc_class":         int(grid_lulc_cls[i]),
            "lulc_name":          str(grid_lulc_name[i]),
            "lulc_score":         s_lulc,
            "ghi_kwh_m2_yr":      round(float(grid_ghi[i]),      1),
            "pv_yield_kwh_kwp":   round(float(grid_ey[i]),       0),
            "ghi_score":          s_ghi,
            "ghi_daily":          round(float(grid_ghi_daily[i]), 3),
            "temp_c":             round(float(grid_temp[i]),      2),
            "temp_score":         s_temp,
            "power_dist_km":      round(float(pwr_dists_km[i]),   3),
            "power_score":        s_power,
            "road_dist_km":       round(float(hwy_dists_km[i]),   3),
            "road_score":         s_road,
            "suitability_score":  round(comp, 3),
            "suitability_class":  suit,
            "sources":            source_meta,
        })

    # ── Score distribution summary ─────────────────────────────────────────────
    df = pd.DataFrame(records)
    log.info("-" * 60)
    log.info(f"Parcels generated : {len(df)}")
    log.info(f"Score range       : {df['suitability_score'].min():.3f} – {df['suitability_score'].max():.3f}")
    log.info(f"Score mean        : {df['suitability_score'].mean():.3f}")
    log.info("Suitability class distribution:")
    for cls, cnt in df["suitability_class"].value_counts().items():
        log.info(f"  {cls:<12s} {cnt:>4d} parcels")

    # ── Save ───────────────────────────────────────────────────────────────────
    json_path = PROC_DIR / "kallakurichi_parcels.json"
    csv_path  = PROC_DIR / "kallakurichi_parcels.csv"

    save_json(records, json_path)
    df.to_csv(csv_path, index=False)

    log.info(f"\nSaved → {json_path}")
    log.info(f"Saved → {csv_path}")
    log.info("Run script 07 for raster-based barren land analysis:")
    log.info("  python scripts/07_lulc_barren_analysis.py")


if __name__ == "__main__":
    main()
