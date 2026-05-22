"""
07_lulc_barren_analysis.py — ESA WorldCover LULC Map + Barren Land Analysis
============================================================================
Downloads ESA WorldCover 2021 v200 raster tiles (10 m) for Kallakurichi district
via GDAL windowed reads from AWS S3 (no full tile download required), then:

  Step 1  Clip and merge two 3°×3° tiles covering the district
  Step 2  Save clipped LULC raster  →  data/raw/kallakurichi_lulc.tif
  Step 3  Generate full LULC class map  →  data/outputs/lulc_map.png
  Step 4  Isolate class 60 (Bare/sparse veg) pixels
  Step 5  Connected-component labelling → identify discrete barren patches
  Step 6  Compute per-patch area (ha, km²) from actual 10 m pixel counts
  Step 7  Attach factor values (GHI, slope, power dist, road dist, temp)
          via nearest-neighbour lookup from existing raw data files
  Step 8  Save outputs:
            data/outputs/barren_map.png
            data/processed/barren_analysis.json
            data/processed/barren_analysis.csv

Requirements:
  pip install rasterio scipy matplotlib pillow numpy requests

Usage: python scripts/07_lulc_barren_analysis.py
"""

import math
import sys
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import ListedColormap
from rasterio.merge import merge
from rasterio.transform import xy as rio_xy
from rasterio.windows import from_bounds
from scipy.ndimage import label as scipy_label

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    CITATIONS,
    ESA_S3_TILES,
    LAT_MAX,
    LAT_MIN,
    LON_MAX,
    LON_MIN,
    LULC_CLASSES,
    OUT_DIR,
    PROC_DIR,
    RAW_DIR,
    TARGET_LULC_CLASS,
)
from utils import (
    get_logger,
    haversine_km,
    load_json,
    nn_interp,
    pixel_area_ha,
    save_json,
)

log = get_logger("07_lulc_barren")


# ─── Step 1 + 2 : Load raster tiles ─────────────────────────────────────────────

def load_lulc_raster():
    """
    Open ESA WorldCover 2021 v200 tiles via /vsicurl/ (GDAL virtual filesystem).
    Performs a windowed read for the district bounding box only — no full tile
    download (~119 MB + ~92 MB tiles are read remotely and trimmed locally).
    """
    log.info("[1/5] Opening ESA WorldCover 2021 tiles via GDAL /vsicurl/ ...")
    datasets = []
    for url in ESA_S3_TILES:
        tile_name = url.split("/")[-1]
        try:
            src = rasterio.open(f"/vsicurl/{url}")
            win = from_bounds(LON_MIN, LAT_MIN, LON_MAX, LAT_MAX, src.transform)
            if win.height > 0 and win.width > 0:
                datasets.append(src)
                log.info(
                    f"  ✓ {tile_name}  →  "
                    f"{int(win.width)} × {int(win.height)} px in district bbox"
                )
            else:
                src.close()
                log.info(f"  – {tile_name}  (no overlap with district bbox)")
        except Exception as exc:
            log.warning(f"  ✗ {tile_name}: {exc}")

    if not datasets:
        raise RuntimeError(
            "No ESA tiles could be opened via /vsicurl/.\n"
            "Check internet connectivity or verify that rasterio is installed "
            "with GDAL network drivers (pip install rasterio[gdal])."
        )

    if len(datasets) == 1:
        src       = datasets[0]
        win       = from_bounds(LON_MIN, LAT_MIN, LON_MAX, LAT_MAX, src.transform)
        data      = src.read(1, window=win)
        transform = src.window_transform(win)
        crs       = src.crs
        src.close()
    else:
        merged, transform = merge(
            datasets, bounds=(LON_MIN, LAT_MIN, LON_MAX, LAT_MAX)
        )
        data = merged[0]
        crs  = datasets[0].crs
        for ds in datasets:
            ds.close()

    log.info(
        f"  Clipped raster: {data.shape[1]} × {data.shape[0]} px  "
        f"(~{data.shape[1]*10/1000:.1f} × {data.shape[0]*10/1000:.1f} km)"
    )

    # Save clipped raster for GIS use
    out_tif = RAW_DIR / "kallakurichi_lulc.tif"
    with rasterio.open(
        out_tif, "w", driver="GTiff",
        height=data.shape[0], width=data.shape[1],
        count=1, dtype=data.dtype,
        crs=crs, transform=transform, compress="lzw",
    ) as dst:
        dst.write(data, 1)
    log.info(f"  Saved clipped raster → {out_tif}")
    return data, transform


# ─── Step 3 : Full LULC class map ────────────────────────────────────────────────

def plot_lulc_map(data: np.ndarray, transform) -> Path:
    log.info("\n[2/5] Generating full LULC class map...")

    present = sorted(int(v) for v in np.unique(data) if v in LULC_CLASSES)
    colours = [LULC_CLASSES[c][1] for c in present]
    cmap    = ListedColormap(colours)

    remapped = np.full_like(data, -1, dtype=np.int16)
    for idx, cls in enumerate(present):
        remapped[data == cls] = idx

    nrows, ncols = data.shape
    extent = [
        transform.c,
        transform.c + ncols * transform.a,
        transform.f + nrows * transform.e,
        transform.f,
    ]

    fig, ax = plt.subplots(figsize=(10, 10), dpi=150)
    ax.imshow(
        remapped, cmap=cmap, vmin=0, vmax=max(len(present) - 1, 1),
        extent=extent, origin="upper", interpolation="nearest", aspect="equal",
    )

    # Legend
    patches = [
        mpatches.Patch(color=LULC_CLASSES[c][1], label=LULC_CLASSES[c][0])
        for c in present
    ]
    ax.legend(handles=patches, loc="lower left", fontsize=8,
              framealpha=0.9, title="ESA WorldCover 2021 v200", title_fontsize=8)

    # Coverage statistics panel
    total_px = int(np.sum(data > 0))
    stats: list[str] = []
    for cls in present:
        px  = int(np.sum(data == cls))
        pct = px / total_px * 100 if total_px else 0
        stats.append(f"{LULC_CLASSES[cls][0]}: {pct:.1f}%")
    ax.text(
        0.98, 0.98, "\n".join(stats),
        transform=ax.transAxes, fontsize=6.5, va="top", ha="right",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", alpha=0.85),
    )

    ax.set_title(
        "Kallakurichi District — ESA WorldCover 2021 (10 m resolution)",
        fontsize=13, fontweight="bold", pad=12,
    )
    ax.set_xlabel("Longitude (°E)", fontsize=9)
    ax.set_ylabel("Latitude (°N)",  fontsize=9)
    ax.tick_params(labelsize=8)
    plt.tight_layout()

    out_path = OUT_DIR / "lulc_map.png"
    plt.savefig(out_path, bbox_inches="tight")
    plt.close()
    log.info(f"  Saved → {out_path}")
    return out_path


# ─── Step 4 + 5 : Isolate barren patches ─────────────────────────────────────────

def analyse_barren(data: np.ndarray, transform):
    log.info(f"\n[3/5] Isolating class {TARGET_LULC_CLASS} "
             f"({LULC_CLASSES[TARGET_LULC_CLASS][0]}) pixels...")

    barren_mask = (data == TARGET_LULC_CLASS)
    n_pixels    = int(np.sum(barren_mask))
    log.info(f"  Bare/sparse pixels: {n_pixels:,}")

    if n_pixels == 0:
        log.warning("  No class-60 pixels found in this area.")
        return barren_mask, [], {}

    centre_lat = (LAT_MIN + LAT_MAX) / 2
    ha_per_px  = pixel_area_ha(transform, centre_lat)
    total_ha   = n_pixels * ha_per_px
    total_km2  = total_ha / 100

    log.info(f"  Pixel resolution  : ~{ha_per_px * 10_000:.0f} m²  "
             f"(~10 × 10 m at {centre_lat:.1f}°N)")
    log.info(f"  Total barren area : {total_ha:,.1f} ha  ({total_km2:.2f} km²)")

    # 8-connected labelling
    labelled, n_patches = scipy_label(barren_mask, structure=np.ones((3, 3), int))
    log.info(f"  Connected patches : {n_patches:,}")

    # Keep only patches ≥ 1 ha
    min_px = max(1, int(1.0 / ha_per_px))
    patches = []
    for pid in range(1, n_patches + 1):
        px_mask = labelled == pid
        px_cnt  = int(np.sum(px_mask))
        if px_cnt < min_px:
            continue
        rows, cols = np.where(px_mask)
        mid_r, mid_c = int(np.mean(rows)), int(np.mean(cols))
        clon, clat = rio_xy(transform, mid_r, mid_c, offset="center")
        patch_ha   = px_cnt * ha_per_px
        patches.append({
            "patch_id":  f"P{pid:05d}",
            "lat":       round(float(clat), 5),
            "lon":       round(float(clon), 5),
            "n_pixels":  px_cnt,
            "area_ha":   round(patch_ha, 3),
            "area_km2":  round(patch_ha / 100, 5),
        })

    patches.sort(key=lambda x: -x["area_ha"])
    log.info(f"  Patches ≥ 1 ha    : {len(patches)}")
    if patches:
        p0 = patches[0]
        log.info(f"  Largest patch     : {p0['area_ha']:.1f} ha  "
                 f"at ({p0['lat']}, {p0['lon']})")

    area_summary = {
        "n_pixels":        n_pixels,
        "ha_per_px":       round(ha_per_px, 6),
        "total_ha":        round(total_ha, 2),
        "total_km2":       round(total_km2, 4),
        "n_patches_total": n_patches,
        "patches_ge_1ha":  len(patches),
    }
    return barren_mask, patches, area_summary


# ─── Step 7 : Attach factor values ───────────────────────────────────────────────

def attach_factors(patches: list[dict]) -> tuple[list[dict], dict]:
    log.info("\n[4/5] Attaching GHI, slope, temperature, and distances...")

    # Load raw data
    srtm_data  = load_json(RAW_DIR / "srtm_elevation.json")
    pvgis_data = load_json(RAW_DIR / "pvgis_ghi.json")
    nasa_data  = load_json(RAW_DIR / "nasa_power_ghi.json")
    pwr_osm    = load_json(RAW_DIR / "osm_power.json")
    hwy_osm    = load_json(RAW_DIR / "osm_highways.json")

    srtm_pts = srtm_data if isinstance(srtm_data, list) else srtm_data.get("points", [])
    pvgis_pts = pvgis_data if isinstance(pvgis_data, list) else pvgis_data.get("points", [])
    nasa_pts  = nasa_data  if isinstance(nasa_data,  list) else nasa_data.get("points", [])

    log.info(
        f"  SRTM: {len(srtm_pts)} pts | PVGIS: {len(pvgis_pts)} pts | "
        f"NASA: {len(nasa_pts)} pts | "
        f"Power elements: {len(pwr_osm.get('elements', []))} | "
        f"Highway elements: {len(hwy_osm.get('elements', []))}"
    )

    # Build coordinate arrays for NN interpolation
    srtm_coords = np.array([[p["lat"], p["lon"]] for p in srtm_pts])
    srtm_elev   = np.array([p.get("elevation_m") or 0.0 for p in srtm_pts])
    pvgis_coords = np.array([[p["lat"], p["lon"]] for p in pvgis_pts])
    pvgis_ghi    = np.array([p.get("ghi_kwh_m2_yr") or p.get("H(i)_y") or 0.0 for p in pvgis_pts])
    pvgis_yield  = np.array([p.get("pv_yield_kwh_kwp") or p.get("E_y") or 0.0 for p in pvgis_pts])
    nasa_coords  = np.array([[p["lat"], p["lon"]] for p in nasa_pts])
    nasa_temp    = np.array([p.get("temp_c") or 0.0 for p in nasa_pts])

    # Compute slope from SRTM via neighbour finite differences
    DEG_M = 111_320.0
    slope_vals = np.zeros(len(srtm_pts))
    for i, p in enumerate(srtm_pts):
        la, lo, e0 = p["lat"], p["lon"], p.get("elevation_m") or 0
        nb = [
            q for q in srtm_pts
            if abs(q["lat"] - la) < 0.04 and abs(q["lon"] - lo) < 0.04 and q is not p
        ]
        if len(nb) >= 2:
            grads = []
            for n in nb:
                dm = math.sqrt(
                    ((n["lat"] - la) * DEG_M) ** 2
                    + ((n["lon"] - lo) * DEG_M * math.cos(math.radians(la))) ** 2
                )
                if dm > 0:
                    grads.append(abs((n.get("elevation_m") or 0) - e0) / dm)
            slope_vals[i] = math.degrees(math.atan(float(np.mean(grads)))) if grads else 0.0

    # Build OSM KD-trees
    from scipy.spatial import cKDTree as _KDTree

    def _osm_tree(osm_json: dict):
        pts: list[list[float]] = []
        node_coords: dict[int, tuple] = {}
        for e in osm_json.get("elements", []):
            if e.get("type") == "node" and "lat" in e:
                node_coords[e["id"]] = (e["lat"], e["lon"])
                pts.append([e["lat"], e["lon"]])
            elif e.get("type") == "way":
                for n in e.get("geometry", []):
                    if "lat" in n:
                        pts.append([n["lat"], n["lon"]])
        return _KDTree(np.array(pts)) if pts else None

    pwr_tree = _osm_tree(pwr_osm)
    hwy_tree = _osm_tree(hwy_osm)

    # Query arrays
    patch_coords = np.array([[p["lat"], p["lon"]] for p in patches])

    elev_vals_p,   _ = nn_interp(srtm_coords,  srtm_elev,   patch_coords)
    slope_vals_p,  _ = nn_interp(srtm_coords,  slope_vals,  patch_coords)
    ghi_vals_p,    _ = nn_interp(pvgis_coords, pvgis_ghi,   patch_coords)
    yield_vals_p,  _ = nn_interp(pvgis_coords, pvgis_yield, patch_coords)
    temp_vals_p,   _ = nn_interp(nasa_coords,  nasa_temp,   patch_coords)

    power_dists_km = (
        pwr_tree.query(patch_coords)[0] * 111.0
        if pwr_tree else np.full(len(patches), 50.0)
    )
    road_dists_km = (
        hwy_tree.query(patch_coords)[0] * 111.0
        if hwy_tree else np.full(len(patches), 30.0)
    )

    enriched = []
    for i, p in enumerate(patches):
        enriched.append({
            **p,
            "elevation_m":       round(float(elev_vals_p[i]),   1),
            "slope_deg":         round(float(slope_vals_p[i]),  2),
            "ghi_kwh_m2_yr":     round(float(ghi_vals_p[i]),    1),
            "pv_yield_kwh_kwp":  round(float(yield_vals_p[i]),  0),
            "temp_c":            round(float(temp_vals_p[i]),   2),
            "power_dist_km":     round(float(power_dists_km[i]), 3),
            "road_dist_km":      round(float(road_dists_km[i]),  3),
        })

    def _mean(key):
        vals = [e[key] for e in enriched if e.get(key) is not None]
        return round(float(np.mean(vals)), 3) if vals else 0.0

    factor_summary = {
        "avg_ghi_kwh_m2_yr":  _mean("ghi_kwh_m2_yr"),
        "avg_slope_deg":      _mean("slope_deg"),
        "avg_temp_c":         _mean("temp_c"),
        "avg_power_dist_km":  _mean("power_dist_km"),
        "avg_road_dist_km":   _mean("road_dist_km"),
        "min_power_dist_km":  round(float(min(e["power_dist_km"] for e in enriched)), 3) if enriched else 0,
        "min_road_dist_km":   round(float(min(e["road_dist_km"]  for e in enriched)), 3) if enriched else 0,
        "max_area_ha":        round(float(max(e["area_ha"]        for e in enriched)), 2) if enriched else 0,
        "total_area_ha":      round(float(sum(e["area_ha"]        for e in enriched)), 2) if enriched else 0,
    }
    return enriched, factor_summary


# ─── Step 8 : Barren land map ─────────────────────────────────────────────────────

def plot_barren_map(data: np.ndarray, transform, patches: list[dict]) -> Path:
    log.info("\n[5/5] Generating barren land highlight map...")

    nrows, ncols = data.shape
    extent = [
        transform.c,
        transform.c + ncols * transform.a,
        transform.f + nrows * transform.e,
        transform.f,
    ]

    # Build RGB display: desaturate non-barren classes, highlight barren in orange
    display = np.zeros((*data.shape, 3), dtype=np.uint8)
    for cls, (_, hex_col, _) in LULC_CLASSES.items():
        mask = (data == cls)
        r = int(hex_col[1:3], 16)
        g = int(hex_col[3:5], 16)
        b = int(hex_col[5:7], 16)
        if cls != TARGET_LULC_CLASS:
            grey = int(0.3 * r + 0.59 * g + 0.11 * b)
            display[mask] = [grey, grey, grey]
        else:
            display[mask] = [255, 140, 0]   # bright orange

    fig, ax = plt.subplots(figsize=(10, 10), dpi=150)
    ax.imshow(display, extent=extent, origin="upper", aspect="equal",
              interpolation="nearest")

    # Patch centroids — size proportional to area
    if patches:
        lats  = [p["lat"] for p in patches]
        lons  = [p["lon"] for p in patches]
        areas = [p["area_ha"] for p in patches]
        max_a = max(areas) if areas else 1
        sizes = [max(20, min(300, a / max_a * 200)) for a in areas]
        ax.scatter(lons, lats, s=sizes, c="#FF4500", edgecolors="white",
                   linewidths=0.5, zorder=5, alpha=0.85, label="Barren patch centroid")

        # Label top-10 largest patches
        for p in patches[:10]:
            ax.annotate(
                f"{p['area_ha']:.0f} ha",
                (p["lon"], p["lat"]),
                textcoords="offset points", xytext=(4, 4),
                fontsize=5.5, color="white", fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.2", fc="#FF4500", alpha=0.7),
            )

        # Stats box
        n         = len(patches)
        total_ha  = sum(p["area_ha"] for p in patches)
        avg_ghi   = sum(p.get("ghi_kwh_m2_yr",  0) for p in patches) / n
        avg_slp   = sum(p.get("slope_deg",       0) for p in patches) / n
        avg_pwr   = sum(p.get("power_dist_km",   0) for p in patches) / n
        avg_rd    = sum(p.get("road_dist_km",    0) for p in patches) / n
        stats_txt = (
            f"Patches ≥ 1 ha : {n}\n"
            f"Total area     : {total_ha:,.0f} ha\n"
            f"Avg GHI        : {avg_ghi:.0f} kWh/m²/yr\n"
            f"Avg slope      : {avg_slp:.1f}°\n"
            f"Avg power dist : {avg_pwr:.1f} km\n"
            f"Avg road dist  : {avg_rd:.1f} km"
        )
        ax.text(0.98, 0.98, stats_txt, transform=ax.transAxes, fontsize=8,
                va="top", ha="right",
                bbox=dict(boxstyle="round,pad=0.5", fc="white", alpha=0.9))

    barren_p = mpatches.Patch(color="#FF8C00", label="Bare/sparse veg (class 60)")
    grey_p   = mpatches.Patch(color="#888888", label="Other land cover (greyed)")
    ax.legend(handles=[barren_p, grey_p], loc="lower left", fontsize=8, framealpha=0.9)

    ax.set_title(
        "Kallakurichi District — Bare/Sparse Vegetation (ESA WorldCover 2021 v200)",
        fontsize=12, fontweight="bold", pad=12,
    )
    ax.set_xlabel("Longitude (°E)", fontsize=9)
    ax.set_ylabel("Latitude (°N)",  fontsize=9)
    ax.tick_params(labelsize=8)
    plt.tight_layout()

    out_path = OUT_DIR / "barren_map.png"
    plt.savefig(out_path, bbox_inches="tight")
    plt.close()
    log.info(f"  Saved → {out_path}")
    return out_path


# ─── Main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=" * 65)
    log.info("  Script 07 — ESA WorldCover LULC + Barren Land Analysis")
    log.info("  Kallakurichi District, Tamil Nadu, India")
    log.info(f"  Bbox: [{LAT_MIN}–{LAT_MAX}°N, {LON_MIN}–{LON_MAX}°E]")
    log.info("=" * 65)

    data, transform = load_lulc_raster()
    plot_lulc_map(data, transform)
    barren_mask, patches, area_summary = analyse_barren(data, transform)

    if not patches:
        log.warning("No barren patches found.  Nothing further to analyse.")
        return

    enriched, factor_summary = attach_factors(patches)
    plot_barren_map(data, transform, enriched)

    # ── Save JSON output ───────────────────────────────────────────────────────
    full_summary = {
        "district":    "Kallakurichi, Tamil Nadu, India",
        "data_source": "ESA WorldCover 2021 v200 (10 m resolution)",
        "lulc_filter": f"Class {TARGET_LULC_CLASS} — "
                       f"{LULC_CLASSES[TARGET_LULC_CLASS][0]}",
        "bbox": {
            "lat_min": LAT_MIN, "lat_max": LAT_MAX,
            "lon_min": LON_MIN, "lon_max": LON_MAX,
        },
        "citation":       CITATIONS["esa_worldcover"],
        **area_summary,
        **factor_summary,
        "top_patches":    enriched[:20],
        "all_patches":    enriched,
    }

    json_path = PROC_DIR / "barren_analysis.json"
    save_json(full_summary, json_path)
    log.info(f"\n  Saved → {json_path}")

    # ── Save CSV output ────────────────────────────────────────────────────────
    import csv
    csv_path = PROC_DIR / "barren_analysis.csv"
    if enriched:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(enriched[0].keys()))
            writer.writeheader()
            writer.writerows(enriched)
        log.info(f"  Saved → {csv_path}")

    # ── Final console summary ──────────────────────────────────────────────────
    log.info("")
    log.info("=" * 65)
    log.info("  RESULTS")
    log.info("=" * 65)
    log.info(f"  Total bare/sparse area   : {area_summary['total_ha']:>10,.1f} ha"
             f"  ({area_summary['total_km2']:.2f} km²)")
    log.info(f"  Patches (connected, 8-nb): {area_summary['n_patches_total']:>10,}")
    log.info(f"  Patches ≥ 1 ha           : {area_summary['patches_ge_1ha']:>10,}")
    log.info(f"  Largest patch            : {factor_summary['max_area_ha']:>10.1f} ha")
    log.info("")
    log.info(f"  Avg GHI                  : {factor_summary['avg_ghi_kwh_m2_yr']:>10.1f} kWh/m²/yr")
    log.info(f"  Avg slope                : {factor_summary['avg_slope_deg']:>10.2f} °")
    log.info(f"  Avg temperature          : {factor_summary['avg_temp_c']:>10.2f} °C")
    log.info(f"  Avg dist. to substation  : {factor_summary['avg_power_dist_km']:>10.2f} km")
    log.info(f"  Avg dist. to highway     : {factor_summary['avg_road_dist_km']:>10.2f} km")
    log.info(f"  Nearest substation       : {factor_summary['min_power_dist_km']:>10.2f} km")
    log.info(f"  Nearest highway          : {factor_summary['min_road_dist_km']:>10.2f} km")
    log.info("")
    log.info("  Output files:")
    log.info("    data/raw/kallakurichi_lulc.tif         ← clipped LULC raster (10 m)")
    log.info("    data/outputs/lulc_map.png              ← full LULC class map")
    log.info("    data/outputs/barren_map.png            ← barren land highlight map")
    log.info("    data/processed/barren_analysis.json   ← full patch statistics")
    log.info("    data/processed/barren_analysis.csv    ← tabular patch data")
    log.info("")
    log.info("  Next: apply filters with script 06:")
    log.info("    python scripts/06_filter_solar_candidates.py")


if __name__ == "__main__":
    main()
