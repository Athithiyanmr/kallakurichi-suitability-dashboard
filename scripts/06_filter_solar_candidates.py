"""
Script 06 — Bare/Sparse Solar Candidate Identification
=======================================================
Filters Kallakurichi district to ESA WorldCover class 60 (Bare/sparse vegetation)
parcels only, then attaches real GHI, slope, temperature, and distance-to-substation,
distance-to-highway values via nearest-neighbour lookup from the raw data files.

Outputs:
  data/processed/solar_candidates.csv   — ranked table
  data/processed/solar_candidates.geojson — for QGIS / Leaflet

Steps:
  1. Re-sample ESA WorldCover on a dense 40×40 grid (1600 points) to find all
     class-60 pixels inside the district bounding box.
  2. For each class-60 point, attach factor values via KD-tree NN lookup from the
     existing raw files (SRTM elevation → slope, PVGIS GHI, NASA POWER temp,
     OSM power lines, OSM highways).
  3. Score each factor 1–4 using the same rubric as script 05.
  4. Compute composite suitability score (equal-weight by default; edit WEIGHTS
     below to customise).
  5. Rank and export.

Run after scripts 01–04 have been executed.
Usage:
  python scripts/06_filter_solar_candidates.py
"""

import json
import math
import time
import os
import csv
import requests
from pathlib import Path

# ─── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent.parent
RAW_DIR     = BASE_DIR / "data" / "raw"
OUT_DIR     = BASE_DIR / "data" / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ─── District bounding box (Kallakurichi, Tamil Nadu) ───────────────────────────
LAT_MIN, LAT_MAX = 11.60, 12.20
LON_MIN, LON_MAX = 78.60, 79.20

# ─── Dense grid for ESA re-sampling ─────────────────────────────────────────────
GRID_N = 40           # 40×40 = 1600 points
BATCH  = 66           # ESA WMS requests per batch

# ─── Equal weights for composite score (adjust as needed) ───────────────────────
WEIGHTS = {
    "slope":  1.0,
    "ghi":    1.0,
    "temp":   1.0,
    "power":  1.0,
    "road":   1.0,
}

# ─── ESA WorldCover class map ────────────────────────────────────────────────────
LULC_MAP = {
    10: "Tree cover",
    20: "Shrubland",
    30: "Grassland",
    40: "Cropland",
    50: "Built-up",
    60: "Bare/sparse veg",
    70: "Snow/ice",
    80: "Water bodies",
    90: "Herbaceous wetland",
    95: "Mangroves",
    100: "Moss/lichen",
}

TARGET_CLASS = 60   # Bare/sparse vegetation only


# ─── Helpers ────────────────────────────────────────────────────────────────────

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def nearest(query_lat, query_lon, points, lat_key="lat", lon_key="lon"):
    """Return the nearest point from a list using Euclidean distance on lat/lon."""
    best, best_d = None, float("inf")
    for p in points:
        d = (p[lat_key] - query_lat) ** 2 + (p[lon_key] - query_lon) ** 2
        if d < best_d:
            best_d, best = d, p
    return best


def slope_score(deg):
    if deg < 3:   return 4
    if deg < 8:   return 3
    if deg < 15:  return 2
    return 1


def ghi_score(kwh):
    if kwh >= 1980: return 4
    if kwh >= 1965: return 3
    if kwh >= 1950: return 2
    return 1


def temp_score(c):
    if c <= 25: return 4
    if c <= 26: return 3
    if c <= 27: return 2
    return 1


def power_score(km):
    if km <= 2:  return 4
    if km <= 5:  return 3
    if km <= 10: return 2
    return 1


def road_score(km):
    if km <= 1:  return 4
    if km <= 3:  return 3
    if km <= 8:  return 2
    return 1


# ─── Step 1: Generate dense grid ────────────────────────────────────────────────

def generate_grid(n=GRID_N):
    lats = [LAT_MIN + (LAT_MAX - LAT_MIN) * i / (n - 1) for i in range(n)]
    lons = [LON_MIN + (LON_MAX - LON_MIN) * j / (n - 1) for j in range(n)]
    return [{"lat": round(lat, 5), "lon": round(lon, 5)} for lat in lats for lon in lons]


# ─── Step 2: Sample ESA WorldCover via Terrascope WMS ───────────────────────────

def fetch_esa_class(lat, lon, session):
    """
    Fetch a single ESA WorldCover 2020 class value for a given lat/lon
    using a 30m WMS GetMap request interpreted as RGB → class code.
    """
    # EPSG:3857 conversion for 30m pixel around point
    R_EARTH = 6378137.0
    x = math.radians(lon) * R_EARTH
    y = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * R_EARTH
    d = 15  # 30m box half-width

    url = (
        "https://services.terrascope.be/wms/v2"
        "?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap"
        "&LAYERS=WORLDCOVER_2020_MAP"
        "&STYLES=&FORMAT=image/png"
        f"&BBOX={x-d},{y-d},{x+d},{y+d}"
        "&WIDTH=1&HEIGHT=1&SRS=EPSG:3857"
    )
    try:
        r = session.get(url, timeout=15)
        r.raise_for_status()
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        rgb = img.getpixel((0, 0))

        # ESA WorldCover canonical RGB → class
        rgb_map = {
            (0, 100, 0):    10,
            (255, 187, 34): 20,
            (255, 255, 76): 30,
            (240, 150, 255): 40,
            (250, 0, 0):    50,
            (180, 180, 180): 60,
            (240, 240, 240): 70,
            (0, 100, 200):  80,
            (0, 150, 160):  90,
            (0, 207, 117):  95,
            (250, 230, 160): 100,
        }

        best_class, best_d = 0, float("inf")
        for ref_rgb, cls in rgb_map.items():
            dist = sum((a - b) ** 2 for a, b in zip(rgb, ref_rgb))
            if dist < best_d:
                best_d, best_class = dist, cls

        # Reject if too far from any known class (likely NoData / ocean)
        if best_d > 15000:
            return None, None

        return best_class, LULC_MAP.get(best_class, f"Class {best_class}")
    except Exception:
        return None, None


# ─── Step 3: Slope from SRTM elevations ─────────────────────────────────────────

def build_slope_lookup(srtm_points):
    """Pre-compute slope (°) for each SRTM point using finite differences."""
    from math import degrees, atan, sqrt
    DEG_TO_M = 111320.0
    result = []
    pts = sorted(srtm_points, key=lambda p: (p["lat"], p["lon"]))
    # Create index for quick neighbour lookup
    index = {(round(p["lat"], 3), round(p["lon"], 3)): p for p in pts}

    for p in pts:
        lat0, lon0, elev0 = p["lat"], p["lon"], p.get("elevation_m", 0)
        dx, dy = 0.03, 0.03  # ~3km spacing

        east  = index.get((round(lat0, 3), round(lon0 + dx, 3)))
        west  = index.get((round(lat0, 3), round(lon0 - dx, 3)))
        north = index.get((round(lat0 + dy, 3), round(lon0, 3)))
        south = index.get((round(lat0 - dy, 3), round(lon0, 3)))

        dz_dx = dz_dy = 0
        if east and west:
            dz_dx = (east["elevation_m"] - west["elevation_m"]) / (2 * dx * DEG_TO_M * math.cos(math.radians(lat0)))
        elif east:
            dz_dx = (east["elevation_m"] - elev0) / (dx * DEG_TO_M * math.cos(math.radians(lat0)))
        elif west:
            dz_dx = (elev0 - west["elevation_m"]) / (dx * DEG_TO_M * math.cos(math.radians(lat0)))

        if north and south:
            dz_dy = (north["elevation_m"] - south["elevation_m"]) / (2 * dy * DEG_TO_M)
        elif north:
            dz_dy = (north["elevation_m"] - elev0) / (dy * DEG_TO_M)
        elif south:
            dz_dy = (elev0 - south["elevation_m"]) / (dy * DEG_TO_M)

        slope = math.degrees(math.atan(math.sqrt(dz_dx ** 2 + dz_dy ** 2)))
        result.append({**p, "slope_deg": round(slope, 2)})

    return result


# ─── Step 4: OSM distance computation ───────────────────────────────────────────

def extract_osm_nodes(osm_json, elem_types=("node", "way", "relation")):
    """Extract all unique lat/lon node positions from an OSM Overpass response."""
    nodes = {}
    for elem in osm_json.get("elements", []):
        if elem.get("type") == "node" and "lat" in elem:
            nodes[elem["id"]] = {"lat": elem["lat"], "lon": elem["lon"]}

    positions = []
    for elem in osm_json.get("elements", []):
        if elem.get("type") == "node" and "lat" in elem:
            positions.append({"lat": elem["lat"], "lon": elem["lon"]})
        elif elem.get("type") == "way":
            for nid in elem.get("nodes", []):
                if nid in nodes:
                    positions.append(nodes[nid])

    # Deduplicate with 4-decimal precision
    seen = set()
    unique = []
    for p in positions:
        key = (round(p["lat"], 4), round(p["lon"], 4))
        if key not in seen:
            seen.add(key)
            unique.append({"lat": p["lat"], "lon": p["lon"]})
    return unique


def min_distance_km(lat, lon, node_list):
    """Fast approximate minimum distance to a list of lat/lon nodes (degrees → km)."""
    best = float("inf")
    for n in node_list:
        # Cheap Euclidean approx first
        approx = math.sqrt((n["lat"] - lat) ** 2 + (n["lon"] - lon) ** 2) * 111.0
        if approx < best * 1.5:  # Only compute haversine for candidates
            d = haversine_km(lat, lon, n["lat"], n["lon"])
            if d < best:
                best = d
    return round(best, 3)


# ─── Main ────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Script 06 — Bare/Sparse Solar Candidate Identification")
    print("=" * 60)

    # ── Load raw data ──────────────────────────────────────────────────────────
    print("\n[1/5] Loading raw data files...")

    with open(RAW_DIR / "srtm_elevation.json") as f:
        srtm_raw = json.load(f)
    srtm_pts = srtm_raw if isinstance(srtm_raw, list) else srtm_raw.get("points", [])
    srtm_with_slope = build_slope_lookup(srtm_pts)
    print(f"      SRTM: {len(srtm_with_slope)} points with slope computed")

    with open(RAW_DIR / "pvgis_ghi.json") as f:
        pvgis_raw = json.load(f)
    pvgis_pts = pvgis_raw if isinstance(pvgis_raw, list) else pvgis_raw.get("points", [])
    print(f"      PVGIS: {len(pvgis_pts)} points")

    with open(RAW_DIR / "nasa_power_ghi.json") as f:
        nasa_raw = json.load(f)
    nasa_pts = nasa_raw if isinstance(nasa_raw, list) else nasa_raw.get("points", [])
    print(f"      NASA POWER: {len(nasa_pts)} points")

    with open(RAW_DIR / "osm_power.json") as f:
        osm_power = json.load(f)
    power_nodes = extract_osm_nodes(osm_power)
    print(f"      OSM power nodes: {len(power_nodes)}")

    with open(RAW_DIR / "osm_highways.json") as f:
        osm_roads = json.load(f)
    road_nodes = extract_osm_nodes(osm_roads)
    print(f"      OSM road nodes: {len(road_nodes)}")

    # ── Generate dense grid ────────────────────────────────────────────────────
    print(f"\n[2/5] Generating {GRID_N}×{GRID_N} = {GRID_N*GRID_N} point grid...")
    grid = generate_grid(GRID_N)

    # ── Sample ESA WorldCover for every grid point ─────────────────────────────
    print(f"\n[3/5] Sampling ESA WorldCover (class 60 filter)...")
    print(f"      This queries Terrascope WMS — may take a few minutes.")

    candidates = []
    session = requests.Session()
    errors = 0

    for i, pt in enumerate(grid):
        cls, name = fetch_esa_class(pt["lat"], pt["lon"], session)

        if (i + 1) % BATCH == 0 or (i + 1) == len(grid):
            pct = (i + 1) / len(grid) * 100
            print(f"      {i+1}/{len(grid)} sampled | class-60 found so far: {len(candidates)} | errors: {errors}")

        if cls is None:
            errors += 1
            continue

        if cls == TARGET_CLASS:
            candidates.append({**pt, "lulc_class": cls, "lulc_name": name})

        time.sleep(0.05)  # ~20 req/s — polite rate

    print(f"\n  ✅ Class 60 (bare/sparse) candidates: {len(candidates)} / {len(grid)} grid points")

    if not candidates:
        print("  ⚠️  No class-60 points found. Check WMS connectivity or try shrubland (class 20).")
        return

    # ── Attach factor values ───────────────────────────────────────────────────
    print(f"\n[4/5] Attaching factor values (slope, GHI, temp, distances)...")

    results = []
    for i, c in enumerate(candidates):
        lat, lon = c["lat"], c["lon"]

        # SRTM slope
        srtm_nn = nearest(lat, lon, srtm_with_slope)
        elev     = srtm_nn.get("elevation_m", 0)
        slope    = srtm_nn.get("slope_deg", 0)

        # PVGIS GHI
        pvgis_nn = nearest(lat, lon, pvgis_pts)
        ghi      = pvgis_nn.get("ghi_kwh_m2_yr", pvgis_nn.get("H_i_opt", 0))
        pv_yield = pvgis_nn.get("pv_yield_kwh_kwp", 0)

        # NASA POWER temperature
        nasa_nn  = nearest(lat, lon, nasa_pts)
        temp     = nasa_nn.get("temp_c", nasa_nn.get("temperature_2m_c", 25.0))

        # OSM distances (haversine to nearest node)
        power_km = min_distance_km(lat, lon, power_nodes)
        road_km  = min_distance_km(lat, lon, road_nodes)

        # Factor scores (1–4)
        s_slope = slope_score(slope)
        s_ghi   = ghi_score(ghi)
        s_temp  = temp_score(temp)
        s_power = power_score(power_km)
        s_road  = road_score(road_km)

        # Composite score (equal weight)
        total_w  = sum(WEIGHTS.values())
        composite = (
            WEIGHTS["slope"] * s_slope +
            WEIGHTS["ghi"]   * s_ghi   +
            WEIGHTS["temp"]  * s_temp  +
            WEIGHTS["power"] * s_power +
            WEIGHTS["road"]  * s_road
        ) / total_w

        if composite >= 3.5:    suit_class = "Very High"
        elif composite >= 2.75: suit_class = "High"
        elif composite >= 2.0:  suit_class = "Moderate"
        else:                   suit_class = "Low"

        results.append({
            "candidate_id":       f"BARE-{i+1:04d}",
            "lat":                round(lat, 5),
            "lon":                round(lon, 5),
            "lulc_class":         c["lulc_class"],
            "lulc_name":          c["lulc_name"],
            "elevation_m":        round(elev, 1),
            "slope_deg":          round(slope, 2),
            "slope_score":        s_slope,
            "ghi_kwh_m2_yr":      round(ghi, 1),
            "pv_yield_kwh_kwp":   round(pv_yield, 0),
            "ghi_score":          s_ghi,
            "temp_c":             round(temp, 2),
            "temp_score":         s_temp,
            "power_dist_km":      power_km,
            "power_score":        s_power,
            "road_dist_km":       road_km,
            "road_score":         s_road,
            "suitability_score":  round(composite, 3),
            "suitability_class":  suit_class,
        })

    # Sort by suitability score descending
    results.sort(key=lambda x: -x["suitability_score"])

    # ── Export ─────────────────────────────────────────────────────────────────
    print(f"\n[5/5] Exporting {len(results)} candidates...")

    # CSV
    csv_path = OUT_DIR / "solar_candidates.csv"
    fieldnames = list(results[0].keys())
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"  ✅ CSV  → {csv_path}")

    # GeoJSON
    geojson = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "metadata": {
            "title": "Kallakurichi Bare/Sparse Solar Candidate Parcels",
            "lulc_filter": "ESA WorldCover 2020 class 60 (Bare/sparse vegetation)",
            "grid": f"{GRID_N}×{GRID_N} = {GRID_N*GRID_N} points",
            "total_candidates": len(results),
            "data_sources": [
                "ESA WorldCover 2020 v100 (Terrascope WMS)",
                "NASA SRTM 30m (OpenTopoData)",
                "PVGIS ERA5 v5.2",
                "NASA POWER v8 MERRA-2",
                "OSM Overpass API (power lines + highways)",
            ],
        },
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
                "properties": {k: v for k, v in r.items() if k not in ("lat", "lon")},
            }
            for r in results
        ],
    }
    geojson_path = OUT_DIR / "solar_candidates.geojson"
    with open(geojson_path, "w") as f:
        json.dump(geojson, f, indent=2)
    print(f"  ✅ GeoJSON → {geojson_path}")

    # ── Summary ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"  Grid size:          {GRID_N}×{GRID_N} = {GRID_N*GRID_N} points")
    print(f"  Class-60 found:     {len(results)}")
    print(f"  Very High suit.:    {sum(1 for r in results if r['suitability_class'] == 'Very High')}")
    print(f"  High suit.:         {sum(1 for r in results if r['suitability_class'] == 'High')}")
    print(f"  Avg GHI:            {sum(r['ghi_kwh_m2_yr'] for r in results)/len(results):.1f} kWh/m²/yr")
    print(f"  Avg slope:          {sum(r['slope_deg'] for r in results)/len(results):.2f}°")
    print(f"  Avg power dist:     {sum(r['power_dist_km'] for r in results)/len(results):.2f} km")
    print(f"  Avg road dist:      {sum(r['road_dist_km'] for r in results)/len(results):.2f} km")
    print()
    print("  Top 5 candidates:")
    for r in results[:5]:
        print(f"    {r['candidate_id']}  lat={r['lat']} lon={r['lon']}  "
              f"score={r['suitability_score']}  class={r['suitability_class']}  "
              f"GHI={r['ghi_kwh_m2_yr']} kWh  slope={r['slope_deg']}°  "
              f"power={r['power_dist_km']} km  road={r['road_dist_km']} km")
    print()
    print(f"  Outputs saved to:  {OUT_DIR}/")
    print("  → solar_candidates.csv")
    print("  → solar_candidates.geojson")


if __name__ == "__main__":
    main()
