"""
08_barren_polygons.py — ESA Barren Land → Real Polygons + Full Factor Analysis
===============================================================================
Pipeline:
  1. Open ESA WorldCover 2021 v200 tiles via GDAL /vsicurl/ (AWS S3 public)
     Clip to Kallakurichi district boundary polygon from district_boundary.json
  2. Mask to barren/sparse veg (class 60) + optionally shrubland (class 20)
  3. Vectorise raster blobs → real polygon geometries (rasterio + shapely)
  4. Simplify + filter small polygons (< 0.5 ha)
  5. For each polygon centroid: attach
       - Area (ha, km²)
       - GHI annual (kWh/m²/yr)  — PVGIS nearest-neighbour
       - Slope (°)               — SRTM NN + finite difference
       - Elevation (m)           — SRTM NN
       - Temperature (°C)        — NASA POWER NN
       - Dist. to power tower (km) — OSM KD-tree
       - Dist. to highway (km)   — OSM KD-tree
       - Suitability score (1–4) + class label
  6. Export data/processed/barren_parcels.geojson  (polygon features)
  7. Export data/processed/barren_parcels.json     (flat records for API)
  8. Export data/processed/barren_parcels.csv

Usage: python scripts/08_barren_polygons.py
"""

import json
import math
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np

# ── GDAL / rasterio ────────────────────────────────────────────────────────────
try:
    import rasterio
    from rasterio.features import shapes as rasterio_shapes
    from rasterio.merge import merge as rasterio_merge
    from rasterio.windows import from_bounds
    from rasterio.mask import mask as rasterio_mask
except ImportError:
    print("ERROR: rasterio not installed. Run: pip install rasterio")
    sys.exit(1)

# ── Shapely ────────────────────────────────────────────────────────────────────
try:
    from shapely.geometry import shape, mapping, MultiPolygon, Polygon
    from shapely.ops import unary_union
except ImportError:
    print("ERROR: shapely not installed. Run: pip install shapely")
    sys.exit(1)

# ── scipy KD-tree ──────────────────────────────────────────────────────────────
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))

RAW_DIR  = Path(__file__).resolve().parent.parent / "data" / "raw"
PROC_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
PROC_DIR.mkdir(parents=True, exist_ok=True)

# ── District bbox (tight, from district_boundary.json) ────────────────────────
LAT_MIN, LAT_MAX = 11.50, 12.08
LON_MIN, LON_MAX = 78.62, 79.46

# ESA WorldCover 2021 v200 — two tiles covering district
ESA_TILES = [
    "https://esa-worldcover.s3.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N09E078_Map.tif",
    "https://esa-worldcover.s3.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N12E078_Map.tif",
]

# Classes to keep (barren + shrubland)
TARGET_CLASSES = {60, 20}   # 60=Bare/sparse veg, 20=Shrubland
CLASS_NAMES    = {60: "Bare/sparse veg", 20: "Shrubland", 10: "Tree cover",
                  30: "Grassland", 40: "Cropland", 50: "Built-up",
                  80: "Water bodies", 70: "Snow/ice", 90: "Herbaceous wetland",
                  95: "Mangroves", 100: "Moss/lichen"}

MIN_AREA_HA    = 0.5     # discard polygons smaller than this
SIMPLIFY_TOL   = 0.0003  # degrees — simplification tolerance (~30 m)

# ── Scoring thresholds ─────────────────────────────────────────────────────────
def score_slope(deg):
    if deg <= 3:   return 4
    if deg <= 7:   return 3
    if deg <= 12:  return 2
    return 1

def score_ghi(ghi):
    if ghi >= 1980: return 4
    if ghi >= 1960: return 3
    if ghi >= 1940: return 2
    return 1

def score_power(km):
    if km <= 2:  return 4
    if km <= 5:  return 3
    if km <= 10: return 2
    return 1

def score_road(km):
    if km <= 1:  return 4
    if km <= 3:  return 3
    if km <= 6:  return 2
    return 1

def score_temp(c):
    if c <= 25: return 4
    if c <= 26: return 3
    if c <= 27: return 2
    return 1

def score_lulc(cls):
    return 4 if cls == 60 else 3  # barren=4, shrubland=3

def composite(scores):
    return round(sum(scores.values()) / len(scores), 3)

def suit_class(score):
    if score >= 3.5:  return "Very High"
    if score >= 2.75: return "High"
    if score >= 2.0:  return "Moderate"
    return "Low"


# ══════════════════════════════════════════════════════════════════════════════
# Step 1: Load + clip ESA raster
# ══════════════════════════════════════════════════════════════════════════════

def load_raster():
    print("=" * 60)
    print("  Step 1: Opening ESA WorldCover 2021 v200 tiles")
    print("=" * 60)

    datasets = []
    for url in ESA_TILES:
        name = url.split("/")[-1]
        try:
            src = rasterio.open(f"/vsicurl/{url}")
            win = from_bounds(LON_MIN, LAT_MIN, LON_MAX, LAT_MAX, src.transform)
            if win.height > 0 and win.width > 0:
                datasets.append(src)
                print(f"  ✓ {name}  ({int(win.width)} × {int(win.height)} px)")
            else:
                src.close()
                print(f"  – {name}  (no overlap)")
        except Exception as e:
            print(f"  ✗ {name}: {e}")

    if not datasets:
        raise RuntimeError("No ESA tiles opened. Check network / rasterio GDAL drivers.")

    if len(datasets) == 1:
        src  = datasets[0]
        win  = from_bounds(LON_MIN, LAT_MIN, LON_MAX, LAT_MAX, src.transform)
        data = src.read(1, window=win)
        transform = src.window_transform(win)
        crs = src.crs
        src.close()
    else:
        merged, transform = rasterio_merge(
            datasets, bounds=(LON_MIN, LAT_MIN, LON_MAX, LAT_MAX)
        )
        data = merged[0]
        crs  = datasets[0].crs
        for ds in datasets:
            ds.close()

    print(f"  Raster shape: {data.shape[1]} × {data.shape[0]} px")
    from collections import Counter
    counts = Counter(data.ravel().tolist())
    print("  Class pixel counts (top 8):")
    for cls, cnt in sorted(counts.items(), key=lambda x: -x[1])[:8]:
        name = CLASS_NAMES.get(cls, f"Class {cls}")
        ha   = cnt * 0.01   # 10m pixel = 0.01 ha
        print(f"    {cls:>3}  {name:<25s}  {cnt:>8,} px  ({ha:,.0f} ha)")

    return data, transform, crs


# ══════════════════════════════════════════════════════════════════════════════
# Step 2: Vectorise barren mask → polygons
# ══════════════════════════════════════════════════════════════════════════════

def vectorise(data, transform):
    print(f"\n  Step 2: Vectorising classes {TARGET_CLASSES} ...")

    # Build binary mask: 1 = target class, 0 = other
    mask = np.isin(data, list(TARGET_CLASSES)).astype(np.uint8)
    # Store original class per pixel (for labelling polygons)
    class_arr = np.where(mask, data, 0).astype(np.uint8)

    n_target = int(mask.sum())
    print(f"  Target pixels: {n_target:,}  (~{n_target * 0.01:,.0f} ha)")

    # Vectorise
    polys = []
    for geom_dict, val in rasterio_shapes(class_arr, mask=mask, transform=transform):
        if val == 0:
            continue
        geom = shape(geom_dict)
        if not geom.is_valid:
            geom = geom.buffer(0)
        # Simplify to reduce vertex count
        geom = geom.simplify(SIMPLIFY_TOL, preserve_topology=True)

        area_ha = geom.area * (111_320 ** 2) / 10_000  # approx via degree area
        if area_ha < MIN_AREA_HA:
            continue

        polys.append({
            "geometry":   geom,
            "lulc_class": int(val),
            "lulc_name":  CLASS_NAMES.get(int(val), f"Class {int(val)}"),
            "area_ha":    round(area_ha, 3),
        })

    print(f"  Polygons ≥ {MIN_AREA_HA} ha: {len(polys):,}")
    if polys:
        areas = [p["area_ha"] for p in polys]
        print(f"  Area range: {min(areas):.1f} – {max(areas):.1f} ha")
        print(f"  Total area: {sum(areas):,.1f} ha  ({sum(areas)/100:.2f} km²)")

    return polys


# ══════════════════════════════════════════════════════════════════════════════
# Step 3: Attach factor values
# ══════════════════════════════════════════════════════════════════════════════

def load_factor_data():
    print("\n  Step 3: Loading factor datasets...")

    def load(path):
        with open(path) as f:
            d = json.load(f)
        return d if isinstance(d, list) else d.get("points", [])

    srtm  = load(RAW_DIR / "srtm_elevation.json")
    pvgis = load(RAW_DIR / "pvgis_ghi.json")
    nasa  = load(RAW_DIR / "nasa_power_ghi.json")

    with open(RAW_DIR / "osm_power.json") as f:
        pwr_osm = json.load(f)
    with open(RAW_DIR / "osm_highways.json") as f:
        hwy_osm = json.load(f)

    print(f"  SRTM: {len(srtm)} pts | PVGIS: {len(pvgis)} pts | NASA: {len(nasa)} pts")
    print(f"  Power elements: {len(pwr_osm.get('elements',[]))} | Highway elements: {len(hwy_osm.get('elements',[]))}")

    # Build KD-trees
    def pts_from_osm(osm):
        coords = []
        for e in osm.get("elements", []):
            if e.get("type") == "node" and "lat" in e:
                coords.append([e["lat"], e["lon"]])
            elif e.get("type") == "way":
                for n in e.get("geometry", []):
                    if "lat" in n:
                        coords.append([n["lat"], n["lon"]])
        return np.array(coords) if coords else None

    pwr_pts = pts_from_osm(pwr_osm)
    hwy_pts = pts_from_osm(hwy_osm)

    pwr_tree = cKDTree(pwr_pts) if pwr_pts is not None and len(pwr_pts) > 0 else None
    hwy_tree = cKDTree(hwy_pts) if hwy_pts is not None and len(hwy_pts) > 0 else None
    print(f"  Power KD-tree: {len(pwr_pts) if pwr_pts is not None else 0} nodes")
    print(f"  Highway KD-tree: {len(hwy_pts) if hwy_pts is not None else 0} nodes")

    # Build factor arrays for NN interpolation
    srtm_coords = np.array([[p["lat"], p["lon"]] for p in srtm])
    srtm_elev   = np.array([p["elevation_m"] or 0 for p in srtm])

    pvgis_coords = np.array([[p["lat"], p["lon"]] for p in pvgis])
    pvgis_ghi    = np.array([p.get("GHI_y") or p.get("ghi_kwh_m2_yr") or 0 for p in pvgis])
    pvgis_yield  = np.array([p.get("E_y") or p.get("pv_yield_kwh_kwp") or 0 for p in pvgis])

    nasa_coords  = np.array([[p["lat"], p["lon"]] for p in nasa])
    nasa_temp    = np.array([p.get("T2M_c") or p.get("temp_c") or 0 for p in nasa])

    # Slope from SRTM (per-point finite differences)
    DEG_M = 111_320.0
    srtm_kdtree = cKDTree(srtm_coords)
    def compute_slope_at(lat, lon, elev):
        dists, idxs = srtm_kdtree.query([lat, lon], k=min(6, len(srtm)))
        grads = []
        for d_deg, idx in zip(dists[1:], idxs[1:]):
            nb = srtm[idx]
            dm = d_deg * DEG_M * math.cos(math.radians(lat))
            de = abs((nb["elevation_m"] or 0) - elev)
            if dm > 0:
                grads.append(de / dm)
        return math.degrees(math.atan(float(np.mean(grads)))) if grads else 0.0

    return {
        "srtm_kdtree":  srtm_kdtree,
        "srtm":         srtm,
        "srtm_coords":  srtm_coords,
        "srtm_elev":    srtm_elev,
        "pvgis_kdtree": cKDTree(pvgis_coords),
        "pvgis_ghi":    pvgis_ghi,
        "pvgis_yield":  pvgis_yield,
        "nasa_kdtree":  cKDTree(nasa_coords),
        "nasa_temp":    nasa_temp,
        "pwr_tree":     pwr_tree,
        "hwy_tree":     hwy_tree,
        "compute_slope": compute_slope_at,
    }


def attach_factors(polys, fd):
    print(f"\n  Attaching factors to {len(polys)} polygons...")

    records = []
    for i, p in enumerate(polys):
        geom  = p["geometry"]
        # Use centroid for factor lookups
        cent  = geom.centroid
        lat, lon = cent.y, cent.x

        query_pt = np.array([[lat, lon]])

        # Elevation
        _, ei = fd["srtm_kdtree"].query(query_pt)
        elev  = float(fd["srtm_elev"][ei[0]])

        # Slope
        slope = fd["compute_slope"](lat, lon, elev)

        # GHI + PV yield
        _, gi = fd["pvgis_kdtree"].query(query_pt)
        ghi   = float(fd["pvgis_ghi"][gi[0]])
        pv_y  = float(fd["pvgis_yield"][gi[0]])

        # Temperature
        _, ni = fd["nasa_kdtree"].query(query_pt)
        temp  = float(fd["nasa_temp"][ni[0]])

        # Power tower distance
        if fd["pwr_tree"]:
            d_deg, _ = fd["pwr_tree"].query(query_pt)
            pwr_km   = float(d_deg[0]) * 111.0
        else:
            pwr_km = 50.0

        # Highway distance
        if fd["hwy_tree"]:
            d_deg, _ = fd["hwy_tree"].query(query_pt)
            hwy_km   = float(d_deg[0]) * 111.0
        else:
            hwy_km = 30.0

        # Scores
        scores = {
            "slope": score_slope(slope),
            "ghi":   score_ghi(ghi),
            "power": score_power(pwr_km),
            "road":  score_road(hwy_km),
            "temp":  score_temp(temp),
            "lulc":  score_lulc(p["lulc_class"]),
        }
        comp = composite(scores)
        suit = suit_class(comp)

        records.append({
            **p,    # geometry, lulc_class, lulc_name, area_ha
            "parcel_id":         f"KLK-{i+1:04d}",
            "lat":               round(lat, 5),
            "lon":               round(lon, 5),
            "area_km2":          round(p["area_ha"] / 100, 5),
            "elevation_m":       round(elev, 1),
            "slope_deg":         round(slope, 2),
            "ghi_kwh_m2_yr":     round(ghi, 1),
            "pv_yield_kwh_kwp":  round(pv_y, 0),
            "temp_c":            round(temp, 2),
            "power_dist_km":     round(pwr_km, 3),
            "road_dist_km":      round(hwy_km, 3),
            "slope_score":       scores["slope"],
            "ghi_score":         scores["ghi"],
            "power_score":       scores["power"],
            "road_score":        scores["road"],
            "temp_score":        scores["temp"],
            "lulc_score":        scores["lulc"],
            "suitability_score": comp,
            "suitability_class": suit,
        })

        if (i + 1) % 20 == 0 or (i + 1) == len(polys):
            print(f"  {i+1}/{len(polys)} done")

    return records


# ══════════════════════════════════════════════════════════════════════════════
# Step 4: Export
# ══════════════════════════════════════════════════════════════════════════════

def export(records):
    print(f"\n  Step 4: Exporting {len(records)} polygon records...")

    # ── GeoJSON ─────────────────────────────────────────────────────────────
    features = []
    for r in records:
        geom    = r["geometry"]
        props   = {k: v for k, v in r.items() if k != "geometry"}
        features.append({
            "type":       "Feature",
            "geometry":   mapping(geom),
            "properties": props,
        })

    geojson = {
        "type": "FeatureCollection",
        "crs":  {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "metadata": {
            "title":        "Kallakurichi Barren Land Polygons — Solar Suitability",
            "district":     "Kallakurichi, Tamil Nadu, India",
            "lulc_source":  "ESA WorldCover 2021 v200 (10 m)",
            "classes":      list(TARGET_CLASSES),
            "min_area_ha":  MIN_AREA_HA,
            "n_polygons":   len(records),
            "total_area_ha": round(sum(r["area_ha"] for r in records), 2),
        },
        "features": features,
    }

    gj_path = PROC_DIR / "barren_parcels.geojson"
    with open(gj_path, "w") as f:
        json.dump(geojson, f, separators=(",", ":"))
    size_kb = gj_path.stat().st_size / 1024
    print(f"  Saved GeoJSON → {gj_path}  ({size_kb:.0f} KB)")

    # ── Flat JSON (for API) ──────────────────────────────────────────────────
    flat = [{k: v for k, v in r.items() if k != "geometry"} for r in records]
    flat_path = PROC_DIR / "barren_parcels.json"
    with open(flat_path, "w") as f:
        json.dump(flat, f, indent=2)
    print(f"  Saved flat JSON → {flat_path}")

    # ── CSV ──────────────────────────────────────────────────────────────────
    import csv
    csv_path = PROC_DIR / "barren_parcels.csv"
    if flat:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(flat[0].keys()))
            writer.writeheader()
            writer.writerows(flat)
    print(f"  Saved CSV → {csv_path}")

    return gj_path


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 65)
    print("  Script 08 — ESA Barren Polygons + Factor Analysis")
    print(f"  Classes: {TARGET_CLASSES}  |  Min area: {MIN_AREA_HA} ha")
    print(f"  Bbox: [{LAT_MIN}–{LAT_MAX}°N, {LON_MIN}–{LON_MAX}°E]")
    print("=" * 65)

    data, transform, crs = load_raster()
    polys                = vectorise(data, transform)

    if not polys:
        print("No polygons found. Check bbox or ESA tile access.")
        return

    factor_data = load_factor_data()
    records     = attach_factors(polys, factor_data)
    gj_path     = export(records)

    # ── Summary ────────────────────────────────────────────────────────────
    scores = [r["suitability_score"] for r in records]
    areas  = [r["area_ha"] for r in records]
    from collections import Counter
    classes = Counter(r["suitability_class"] for r in records)
    lulc_d  = Counter(r["lulc_name"] for r in records)

    print("\n" + "=" * 65)
    print("  RESULTS")
    print("=" * 65)
    print(f"  Polygons          : {len(records)}")
    print(f"  Total area        : {sum(areas):,.1f} ha  ({sum(areas)/100:.2f} km²)")
    print(f"  Largest polygon   : {max(areas):.1f} ha")
    print(f"  Score range       : {min(scores):.3f} – {max(scores):.3f}")
    print(f"  Score mean        : {sum(scores)/len(scores):.3f}")
    print()
    print("  Suitability class distribution:")
    for cls in ("Very High", "High", "Moderate", "Low"):
        print(f"    {cls:<12s}: {classes.get(cls, 0)}")
    print()
    print("  LULC breakdown:")
    for name, cnt in lulc_d.most_common():
        a = sum(r["area_ha"] for r in records if r["lulc_name"] == name)
        print(f"    {name:<25s}: {cnt} polygons  ({a:,.1f} ha)")
    print()
    print(f"  GeoJSON → {gj_path}")
    print("  Copy to dashboard: cp data/processed/barren_parcels.geojson ../kallakurichi-sig/server/")


if __name__ == "__main__":
    main()
