"""
Script 07 — ESA WorldCover LULC Map + Barren Land Analysis
===========================================================
Downloads the actual ESA WorldCover 2021 v200 raster (10 m) for Kallakurichi
district via windowed read (no full tile download), then:

  1. Clips and merges the two 3°×3° tiles that cover the district
  2. Saves the clipped LULC raster  →  data/raw/kallakurichi_lulc.tif
  3. Produces a full LULC class map  →  data/outputs/lulc_map.png
  4. Isolates class-60 (Bare/sparse veg) pixels
  5. Computes:
       - Total barren area  (ha and km²)
       - Per-patch stats after connected-component labelling
  6. Attaches factor values to each barren pixel/patch via NN lookup from the
     existing raw files (PVGIS GHI, SRTM slope, OSM power dist, OSM road dist)
  7. Saves summary stats  →  data/processed/barren_analysis.json
                          →  data/processed/barren_analysis.csv
                          →  data/outputs/barren_map.png

Requirements (all standard in a geo Python environment):
  pip install rasterio geopandas numpy scipy matplotlib pillow requests
"""

import json
import math
import os
import csv
import warnings
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import ListedColormap
import rasterio
from rasterio.windows import from_bounds
from rasterio.merge import merge
from rasterio.transform import xy as rio_xy
from scipy.ndimage import label as scipy_label

warnings.filterwarnings("ignore")

# ─── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent.parent
RAW_DIR     = BASE_DIR / "data" / "raw"
OUT_DIR     = BASE_DIR / "data" / "outputs"
PROC_DIR    = BASE_DIR / "data" / "processed"
for d in (OUT_DIR, PROC_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ─── District bounding box ───────────────────────────────────────────────────────
LAT_MIN, LAT_MAX = 11.55, 12.25
LON_MIN, LON_MAX = 78.55, 79.25

# ─── ESA WorldCover 2021 v200 tiles (public AWS S3) ─────────────────────────────
ESA_TILES = [
    "https://esa-worldcover.s3.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N12E078_Map.tif",
    "https://esa-worldcover.s3.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N09E078_Map.tif",
]

# ─── ESA WorldCover class definitions ───────────────────────────────────────────
LULC_CLASSES = {
    10:  ("Tree cover",           "#006400"),
    20:  ("Shrubland",            "#FFBB22"),
    30:  ("Grassland",            "#FFFF4C"),
    40:  ("Cropland",             "#F096FF"),
    50:  ("Built-up",             "#FA0000"),
    60:  ("Bare/sparse veg",      "#B4B4B4"),  # ← TARGET
    70:  ("Snow/ice",             "#F0F0F0"),
    80:  ("Water bodies",         "#0064C8"),
    90:  ("Herbaceous wetland",   "#0096A0"),
    95:  ("Mangroves",            "#00CF75"),
    100: ("Moss/lichen",          "#FAE6A0"),
}
TARGET_CLASS = 60

# ─── Helpers ────────────────────────────────────────────────────────────────────

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def nearest_value(query_lat, query_lon, points, value_key, lat_key="lat", lon_key="lon"):
    best_val, best_d = None, float("inf")
    for p in points:
        d = (p[lat_key] - query_lat)**2 + (p[lon_key] - query_lon)**2
        if d < best_d:
            best_d = d
            best_val = p.get(value_key)
    return best_val


def min_dist_to_nodes(lat, lon, nodes):
    """Minimum haversine distance (km) to a list of {lat, lon} node dicts."""
    best = float("inf")
    for n in nodes:
        approx = math.sqrt((n["lat"] - lat)**2 + (n["lon"] - lon)**2) * 111.0
        if approx < best * 1.5:
            d = haversine_km(lat, lon, n["lat"], n["lon"])
            if d < best:
                best = d
    return round(best, 3)


def extract_nodes(osm_json):
    node_coords = {}
    for e in osm_json.get("elements", []):
        if e.get("type") == "node" and "lat" in e:
            node_coords[e["id"]] = (e["lat"], e["lon"])
    positions = []
    seen = set()
    for e in osm_json.get("elements", []):
        if e.get("type") == "node" and "lat" in e:
            key = (round(e["lat"], 4), round(e["lon"], 4))
            if key not in seen:
                seen.add(key)
                positions.append({"lat": e["lat"], "lon": e["lon"]})
        elif e.get("type") == "way":
            for nid in e.get("nodes", []):
                if nid in node_coords:
                    lat, lon = node_coords[nid]
                    key = (round(lat, 4), round(lon, 4))
                    if key not in seen:
                        seen.add(key)
                        positions.append({"lat": lat, "lon": lon})
    return positions


def pixel_area_ha(transform, lat):
    """Area in hectares of one 10m pixel at a given latitude."""
    # At 10m resolution in geographic CRS, pixel size in degrees
    res_deg = abs(transform.a)  # degrees per pixel (longitude direction)
    # Convert to metres
    lon_m = res_deg * math.cos(math.radians(lat)) * 111320
    lat_m = abs(transform.e) * 111320
    area_m2 = lon_m * lat_m
    return area_m2 / 10000  # ha

# ─── Step 1: Read + clip ESA tiles ───────────────────────────────────────────────

def load_lulc_raster():
    print("[1/5] Reading ESA WorldCover 2021 tiles (windowed, no full download)...")
    datasets = []
    for url in ESA_TILES:
        try:
            src = rasterio.open(f"/vsicurl/{url}")
            win = from_bounds(LON_MIN, LAT_MIN, LON_MAX, LAT_MAX, src.transform)
            if win.height > 0 and win.width > 0:
                datasets.append(src)
                print(f"  ✓ {url.split('/')[-1][:50]}  →  "
                      f"{int(win.width)}×{int(win.height)} px")
            else:
                src.close()
                print(f"  – No overlap: {url.split('/')[-1][:50]}")
        except Exception as e:
            print(f"  ✗ Could not open {url.split('/')[-1]}: {e}")

    if not datasets:
        raise RuntimeError("No ESA tiles could be opened. Check connectivity.")

    if len(datasets) == 1:
        src = datasets[0]
        win = from_bounds(LON_MIN, LAT_MIN, LON_MAX, LAT_MAX, src.transform)
        data = src.read(1, window=win)
        transform = src.window_transform(win)
        crs = src.crs
        src.close()
    else:
        # Merge tiles then crop
        merged, transform = merge(datasets, bounds=(LON_MIN, LAT_MIN, LON_MAX, LAT_MAX))
        data = merged[0]
        crs = datasets[0].crs
        for ds in datasets:
            ds.close()

    print(f"  Clipped raster: {data.shape[1]}×{data.shape[0]} px  "
          f"(~{data.shape[1]*10/1000:.1f} × {data.shape[0]*10/1000:.1f} km)")

    # Save clipped raster
    out_tif = RAW_DIR / "kallakurichi_lulc.tif"
    with rasterio.open(
        out_tif, "w", driver="GTiff",
        height=data.shape[0], width=data.shape[1],
        count=1, dtype=data.dtype,
        crs=crs, transform=transform,
        compress="lzw",
    ) as dst:
        dst.write(data, 1)
    print(f"  Saved → {out_tif}")

    return data, transform, crs

# ─── Step 2: LULC class map plot ─────────────────────────────────────────────────

def plot_lulc_map(data, transform):
    print("\n[2/5] Generating LULC class map...")

    # Build colourmap aligned to class values
    present_classes = sorted(set(int(v) for v in np.unique(data) if v in LULC_CLASSES))
    cmap_colours = [LULC_CLASSES[c][1] for c in present_classes]
    cmap = ListedColormap(cmap_colours)

    # Remap raster values → indices
    remapped = np.full_like(data, -1, dtype=np.int16)
    for idx, cls in enumerate(present_classes):
        remapped[data == cls] = idx

    # Extent for imshow (lon_min, lon_max, lat_min, lat_max)
    nrows, ncols = data.shape
    lon_min_r = transform.c
    lon_max_r = transform.c + ncols * transform.a
    lat_max_r = transform.f
    lat_min_r = transform.f + nrows * transform.e
    extent = [lon_min_r, lon_max_r, lat_min_r, lat_max_r]

    fig, ax = plt.subplots(figsize=(10, 10), dpi=150)
    ax.imshow(remapped, cmap=cmap, vmin=0, vmax=len(present_classes)-1,
              extent=extent, origin="upper", interpolation="nearest",
              aspect="equal")

    # Legend
    patches = [
        mpatches.Patch(color=LULC_CLASSES[c][1], label=LULC_CLASSES[c][0])
        for c in present_classes
    ]
    ax.legend(handles=patches, loc="lower left", fontsize=8,
              framealpha=0.9, title="ESA WorldCover 2021", title_fontsize=8)

    ax.set_title("Kallakurichi District — ESA WorldCover 2021 (10 m)",
                 fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Longitude", fontsize=9)
    ax.set_ylabel("Latitude", fontsize=9)
    ax.tick_params(labelsize=8)

    # Add class coverage labels
    total_px = np.sum(data != 0)
    stats_text = []
    for cls in present_classes:
        px = int(np.sum(data == cls))
        pct = px / total_px * 100 if total_px > 0 else 0
        stats_text.append(f"{LULC_CLASSES[cls][0]}: {pct:.1f}%")

    ax.text(0.98, 0.98, "\n".join(stats_text),
            transform=ax.transAxes, fontsize=6.5,
            verticalalignment="top", horizontalalignment="right",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="white", alpha=0.85))

    plt.tight_layout()
    out_path = OUT_DIR / "lulc_map.png"
    plt.savefig(out_path, bbox_inches="tight")
    plt.close()
    print(f"  Saved → {out_path}")
    return out_path

# ─── Step 3: Isolate barren pixels ───────────────────────────────────────────────

def analyse_barren(data, transform):
    print("\n[3/5] Isolating class-60 (Bare/sparse veg) pixels...")

    barren_mask = (data == TARGET_CLASS)
    n_pixels    = int(np.sum(barren_mask))
    print(f"  Bare/sparse pixels: {n_pixels:,}")

    if n_pixels == 0:
        print("  ⚠️  No class-60 pixels found in this area.")
        return barren_mask, [], {}

    # Pixel area at district centre latitude
    centre_lat = (LAT_MIN + LAT_MAX) / 2
    ha_per_px  = pixel_area_ha(transform, centre_lat)
    total_ha   = n_pixels * ha_per_px
    total_km2  = total_ha / 100

    print(f"  Pixel size: ~{ha_per_px*10000:.0f} m²  (~10×10 m at {centre_lat:.1f}°N)")
    print(f"  Total barren area: {total_ha:,.1f} ha  ({total_km2:.2f} km²)")

    # Connected components → patches
    structure = np.ones((3, 3), dtype=int)  # 8-connected
    labelled, n_patches = scipy_label(barren_mask, structure=structure)
    print(f"  Connected patches: {n_patches:,}")

    # Per-patch stats (only patches ≥ 1 ha → ≥ ~100 px at 10m)
    MIN_PX = max(1, int(1.0 / ha_per_px))
    patches = []
    for pid in range(1, n_patches + 1):
        px_mask = (labelled == pid)
        px_count = int(np.sum(px_mask))
        if px_count < MIN_PX:
            continue
        rows, cols = np.where(px_mask)
        # Centroid in geographic coords
        mid_row = int(np.mean(rows))
        mid_col = int(np.mean(cols))
        clon, clat = rio_xy(transform, mid_row, mid_col, offset="center")
        patch_ha = px_count * ha_per_px
        patches.append({
            "patch_id":   f"P{pid:05d}",
            "lat":        round(float(clat), 5),
            "lon":        round(float(clon), 5),
            "n_pixels":   px_count,
            "area_ha":    round(patch_ha, 3),
            "area_km2":   round(patch_ha / 100, 5),
        })

    patches.sort(key=lambda x: -x["area_ha"])
    print(f"  Patches ≥ 1 ha: {len(patches)}")
    if patches:
        print(f"  Largest patch: {patches[0]['area_ha']:.1f} ha at "
              f"({patches[0]['lat']}, {patches[0]['lon']})")

    summary = {
        "n_pixels":   n_pixels,
        "ha_per_px":  round(ha_per_px, 6),
        "total_ha":   round(total_ha, 2),
        "total_km2":  round(total_km2, 4),
        "n_patches":  n_patches,
        "patches_ge_1ha": len(patches),
    }
    return barren_mask, patches, summary

# ─── Step 4: Attach factor values to patches ─────────────────────────────────────

def attach_factors(patches):
    print("\n[4/5] Attaching GHI, slope, power distance, road distance...")

    # Load raw data
    with open(RAW_DIR / "srtm_elevation.json") as f:
        srtm_raw = json.load(f)
    srtm_pts = srtm_raw if isinstance(srtm_raw, list) else srtm_raw.get("points", [])

    # Compute slope for SRTM points
    DEG_M = 111320.0
    srtm_with_slope = []
    for p in srtm_pts:
        # Simple neighbourhood slope estimation
        lat0, lon0, e0 = p["lat"], p["lon"], p.get("elevation_m", 0)
        # Find neighbours
        ns = [q for q in srtm_pts if abs(q["lat"]-lat0)<0.04 and abs(q["lon"]-lon0)<0.04 and q is not p]
        if len(ns) >= 2:
            dz_vals = []
            for nb in ns:
                dist_m = math.sqrt(
                    ((nb["lat"]-lat0)*DEG_M)**2 +
                    ((nb["lon"]-lon0)*DEG_M*math.cos(math.radians(lat0)))**2
                )
                if dist_m > 0:
                    dz_vals.append(abs(nb.get("elevation_m",0) - e0) / dist_m)
            grad = float(np.mean(dz_vals)) if dz_vals else 0.0
        else:
            grad = 0.0
        slope = math.degrees(math.atan(grad))
        srtm_with_slope.append({**p, "slope_deg": round(slope, 2)})

    with open(RAW_DIR / "pvgis_ghi.json") as f:
        pvgis_raw = json.load(f)
    pvgis_pts = pvgis_raw if isinstance(pvgis_raw, list) else pvgis_raw.get("points", [])

    with open(RAW_DIR / "nasa_power_ghi.json") as f:
        nasa_raw = json.load(f)
    nasa_pts = nasa_raw if isinstance(nasa_raw, list) else nasa_raw.get("points", [])

    with open(RAW_DIR / "osm_power.json") as f:
        power_nodes = extract_nodes(json.load(f))
    with open(RAW_DIR / "osm_highways.json") as f:
        road_nodes = extract_nodes(json.load(f))

    print(f"  SRTM: {len(srtm_with_slope)} pts | PVGIS: {len(pvgis_pts)} pts | "
          f"Power nodes: {len(power_nodes)} | Road nodes: {len(road_nodes)}")

    enriched = []
    for p in patches:
        lat, lon = p["lat"], p["lon"]

        slope   = nearest_value(lat, lon, srtm_with_slope, "slope_deg")   or 0.0
        elev    = nearest_value(lat, lon, srtm_with_slope, "elevation_m") or 0.0
        ghi     = nearest_value(lat, lon, pvgis_pts, "ghi_kwh_m2_yr")     or 0.0
        pv_yld  = nearest_value(lat, lon, pvgis_pts, "pv_yield_kwh_kwp")  or 0.0
        temp    = nearest_value(lat, lon, nasa_pts, "temp_c")             or 0.0

        power_km = min_dist_to_nodes(lat, lon, power_nodes)
        road_km  = min_dist_to_nodes(lat, lon, road_nodes)

        enriched.append({
            **p,
            "elevation_m":    round(elev, 1),
            "slope_deg":      round(slope, 2),
            "ghi_kwh_m2_yr":  round(ghi, 1),
            "pv_yield_kwh_kwp": round(pv_yld, 0),
            "temp_c":         round(temp, 2),
            "power_dist_km":  power_km,
            "road_dist_km":   road_km,
        })

    return enriched, {
        "avg_ghi_kwh_m2_yr":   round(float(np.mean([e["ghi_kwh_m2_yr"]  for e in enriched])), 2) if enriched else 0,
        "avg_slope_deg":       round(float(np.mean([e["slope_deg"]       for e in enriched])), 3) if enriched else 0,
        "avg_power_dist_km":   round(float(np.mean([e["power_dist_km"]   for e in enriched])), 3) if enriched else 0,
        "avg_road_dist_km":    round(float(np.mean([e["road_dist_km"]    for e in enriched])), 3) if enriched else 0,
        "avg_temp_c":          round(float(np.mean([e["temp_c"]          for e in enriched])), 2) if enriched else 0,
        "min_power_dist_km":   round(float(min(e["power_dist_km"] for e in enriched)), 3) if enriched else 0,
        "min_road_dist_km":    round(float(min(e["road_dist_km"]  for e in enriched)), 3) if enriched else 0,
        "max_area_ha":         round(float(max(e["area_ha"] for e in enriched)), 2) if enriched else 0,
        "total_area_ha":       round(float(sum(e["area_ha"] for e in enriched)), 2) if enriched else 0,
    }

# ─── Step 5: Barren map plot ──────────────────────────────────────────────────────

def plot_barren_map(data, transform, enriched_patches):
    print("\n[5/5] Generating barren land map...")

    nrows, ncols = data.shape
    lon_min_r = transform.c
    lon_max_r = transform.c + ncols * transform.a
    lat_max_r = transform.f
    lat_min_r = transform.f + nrows * transform.e
    extent = [lon_min_r, lon_max_r, lat_min_r, lat_max_r]

    # Base: grey LULC, highlight barren in red-orange
    display = np.zeros((*data.shape, 3), dtype=np.uint8)
    for cls, (name, hex_col) in LULC_CLASSES.items():
        mask = (data == cls)
        r = int(hex_col[1:3], 16)
        g = int(hex_col[3:5], 16)
        b = int(hex_col[5:7], 16)
        # Desaturate non-barren classes to grey
        if cls != TARGET_CLASS:
            grey = int(0.3*r + 0.59*g + 0.11*b)
            display[mask] = [grey, grey, grey]
        else:
            display[mask] = [255, 140, 0]  # bright orange for barren

    fig, ax = plt.subplots(figsize=(10, 10), dpi=150)
    ax.imshow(display, extent=extent, origin="upper", aspect="equal",
              interpolation="nearest")

    # Plot patch centroids (sized by area)
    if enriched_patches:
        lats = [p["lat"] for p in enriched_patches]
        lons = [p["lon"] for p in enriched_patches]
        areas = [p["area_ha"] for p in enriched_patches]
        max_a = max(areas) if areas else 1
        sizes = [max(20, min(300, a / max_a * 200)) for a in areas]
        ax.scatter(lons, lats, s=sizes, c="#FF4500", edgecolors="white",
                   linewidths=0.5, zorder=5, alpha=0.85, label="Barren patch centroid")

        # Label top-10 largest
        for p in enriched_patches[:10]:
            ax.annotate(
                f"{p['area_ha']:.0f} ha",
                (p["lon"], p["lat"]),
                textcoords="offset points", xytext=(4, 4),
                fontsize=5.5, color="white",
                fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.2", fc="#FF4500", alpha=0.7),
            )

    ax.set_title(
        "Kallakurichi District — Bare/Sparse Vegetation (ESA WorldCover 2021)",
        fontsize=12, fontweight="bold", pad=12,
    )
    ax.set_xlabel("Longitude", fontsize=9)
    ax.set_ylabel("Latitude", fontsize=9)
    ax.tick_params(labelsize=8)

    # Legend
    barren_patch = mpatches.Patch(color="#FF8C00", label="Bare/sparse veg (class 60)")
    grey_patch   = mpatches.Patch(color="#888888", label="Other land cover (greyed)")
    ax.legend(handles=[barren_patch, grey_patch], loc="lower left",
              fontsize=8, framealpha=0.9)

    # Stats box
    if enriched_patches:
        n = len(enriched_patches)
        total_ha = sum(p["area_ha"] for p in enriched_patches)
        avg_ghi  = sum(p["ghi_kwh_m2_yr"] for p in enriched_patches) / n
        avg_slp  = sum(p["slope_deg"] for p in enriched_patches) / n
        avg_pwr  = sum(p["power_dist_km"] for p in enriched_patches) / n
        avg_rd   = sum(p["road_dist_km"] for p in enriched_patches) / n
        stats_text = (
            f"Patches (≥1 ha): {n}\n"
            f"Total area: {total_ha:,.0f} ha\n"
            f"Avg GHI: {avg_ghi:.0f} kWh/m²/yr\n"
            f"Avg slope: {avg_slp:.1f}°\n"
            f"Avg power dist: {avg_pwr:.1f} km\n"
            f"Avg road dist: {avg_rd:.1f} km"
        )
        ax.text(0.98, 0.98, stats_text,
                transform=ax.transAxes, fontsize=8,
                va="top", ha="right",
                bbox=dict(boxstyle="round,pad=0.5", fc="white", alpha=0.9))

    plt.tight_layout()
    out_path = OUT_DIR / "barren_map.png"
    plt.savefig(out_path, bbox_inches="tight")
    plt.close()
    print(f"  Saved → {out_path}")
    return out_path

# ─── Main ────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 65)
    print("  Script 07 — ESA LULC Raster + Barren Land Analysis")
    print("  Kallakurichi District, Tamil Nadu")
    print("=" * 65)

    # 1. Load raster
    data, transform, crs = load_lulc_raster()

    # 2. LULC class map
    plot_lulc_map(data, transform)

    # 3. Isolate barren + connected patches
    barren_mask, patches, area_summary = analyse_barren(data, transform)

    if not patches:
        print("\n⚠️  No patches found — nothing to analyse further.")
        return

    # 4. Attach GHI, slope, distances
    enriched, factor_summary = attach_factors(patches)

    # 5. Barren map
    plot_barren_map(data, transform, enriched)

    # 6. Save results
    full_summary = {
        "district":    "Kallakurichi, Tamil Nadu",
        "data_source": "ESA WorldCover 2021 v200 (10 m resolution)",
        "lulc_filter": "Class 60 — Bare/sparse vegetation",
        "bbox":        {"lat_min": LAT_MIN, "lat_max": LAT_MAX,
                        "lon_min": LON_MIN, "lon_max": LON_MAX},
        **area_summary,
        **factor_summary,
        "top_patches": enriched[:20],
    }

    json_path = PROC_DIR / "barren_analysis.json"
    with open(json_path, "w") as f:
        json.dump(full_summary, f, indent=2)
    print(f"\n  Saved → {json_path}")

    csv_path = PROC_DIR / "barren_analysis.csv"
    if enriched:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(enriched[0].keys()))
            writer.writeheader()
            writer.writerows(enriched)
    print(f"  Saved → {csv_path}")

    # ── Final summary ──────────────────────────────────────────────────────────
    print()
    print("=" * 65)
    print("  RESULTS")
    print("=" * 65)
    print(f"  Total bare/sparse area:   {area_summary['total_ha']:>10,.1f} ha"
          f"  ({area_summary['total_km2']:.2f} km²)")
    print(f"  Connected patches (≥1 ha): {area_summary['patches_ge_1ha']:>8,}")
    print(f"  Largest patch:             {factor_summary['max_area_ha']:>8.1f} ha")
    print()
    print(f"  Avg GHI:                  {factor_summary['avg_ghi_kwh_m2_yr']:>8.1f} kWh/m²/yr")
    print(f"  Avg slope:                {factor_summary['avg_slope_deg']:>8.2f} °")
    print(f"  Avg temp:                 {factor_summary['avg_temp_c']:>8.2f} °C")
    print(f"  Avg dist. to substation:  {factor_summary['avg_power_dist_km']:>8.2f} km")
    print(f"  Avg dist. to highway:     {factor_summary['avg_road_dist_km']:>8.2f} km")
    print(f"  Nearest substation:       {factor_summary['min_power_dist_km']:>8.2f} km")
    print(f"  Nearest highway:          {factor_summary['min_road_dist_km']:>8.2f} km")
    print()
    print("  Outputs:")
    print(f"    data/raw/kallakurichi_lulc.tif       ← clipped LULC raster")
    print(f"    data/outputs/lulc_map.png            ← full LULC class map")
    print(f"    data/outputs/barren_map.png          ← barren parcels highlighted")
    print(f"    data/processed/barren_analysis.json  ← full stats + top patches")
    print(f"    data/processed/barren_analysis.csv   ← all patches tabular")


if __name__ == "__main__":
    main()
