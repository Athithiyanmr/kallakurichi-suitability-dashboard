"""
Script 05 — Data Processing Pipeline
Combines all raw data sources into a unified analysis dataset.

Processing steps:
  1. Load raw JSON files (SRTM, PVGIS, NASA POWER, ESA LULC, OSM)
  2. Build 20×20 analysis grid over Kallakurichi district
  3. KD-tree nearest-neighbour interpolation for each factor
  4. Compute slope from SRTM elevation finite differences
  5. Distance-to-feature calculations (power lines, roads)
  6. Score each factor on 1–4 suitability scale
  7. Output: data/processed/kallakurichi_parcels.json + .csv

Output fields:
  parcel_id, village, lat, lon, elevation_m, slope_deg, slope_score,
  lulc_class, lulc_name, lulc_score, ghi_kwh_m2_yr, pv_yield_kwh_kwp,
  ghi_score, ghi_daily, temp_c, temp_score, power_dist_km, power_score,
  road_dist_km, road_score, sources
"""

import json, numpy as np, pandas as pd, os
from scipy.spatial import cKDTree
import warnings; warnings.filterwarnings("ignore")

ROOT = os.path.join(os.path.dirname(__file__), "..")
RAW  = os.path.join(ROOT, "data", "raw")
PROC = os.path.join(ROOT, "data", "processed")
os.makedirs(PROC, exist_ok=True)

# ── Grid definition ───────────────────────────────────────────────────────────
LAT_G = np.linspace(11.62, 12.08, 20)
LON_G = np.linspace(78.63, 79.33, 20)

# ── Load raw sources ──────────────────────────────────────────────────────────
def load_json(fname):
    with open(os.path.join(RAW, fname)) as f:
        return json.load(f)

elev_raw = load_json("srtm_elevation.json")["points"]
ghi_raw  = load_json("pvgis_ghi.json")["points"]
nasa_raw = load_json("nasa_power_ghi.json")["points"]
lulc_raw = load_json("esa_worldcover_lulc.json")["points"]
pwr_raw  = load_json("osm_power.json")["elements"]
hwy_raw  = load_json("osm_highways.json")["elements"]

print(f"Loaded: {len(elev_raw)} elev · {len(ghi_raw)} pvgis · {len(nasa_raw)} nasa "
      f"· {len(lulc_raw)} lulc · {len(pwr_raw)} pwr · {len(hwy_raw)} hwy elements")

# ── Build analysis grid ───────────────────────────────────────────────────────
lons, lats = np.meshgrid(LON_G, LAT_G)
grid_pts   = np.column_stack([lats.ravel(), lons.ravel()])
print(f"Analysis grid: {len(grid_pts)} points ({LAT_G.size}×{LON_G.size})")


# ── KD-tree nearest-neighbour interpolation ───────────────────────────────────
def nn_interp(src_pts, src_vals, query_pts):
    """Return nearest-neighbour interpolated values and distances."""
    tree = cKDTree(src_pts)
    dists, idxs = tree.query(query_pts)
    return np.asarray(src_vals)[idxs], dists


# ── 1. SRTM Elevation + Slope ─────────────────────────────────────────────────
elev_pts  = np.array([[p["lat"], p["lon"]] for p in elev_raw])
elev_vals = np.array([p["elevation_m"] for p in elev_raw])
grid_elev, _ = nn_interp(elev_pts, elev_vals, grid_pts)


def compute_slope(elev_flat, lat_g, lon_g):
    """Approximate slope (degrees) from gridded elevation using finite differences."""
    eg = elev_flat.reshape(len(lat_g), len(lon_g))
    lat_sp = (lat_g[1] - lat_g[0]) * 111320          # metres per lat step
    lon_sp = (lon_g[1] - lon_g[0]) * 111320 * np.cos(np.radians(lat_g.mean()))
    dy = np.gradient(eg, axis=0) / lat_sp
    dx = np.gradient(eg, axis=1) / lon_sp
    return np.degrees(np.arctan(np.sqrt(dx**2 + dy**2))).ravel()


grid_slope = compute_slope(grid_elev, LAT_G, LON_G)

def slope_score(s):
    if s > 15: return 1
    elif s > 8: return 2
    elif s > 3: return 3
    return 4

grid_slope_score = np.array([slope_score(s) for s in grid_slope])
print(f"Slope: {grid_slope.min():.1f}°–{grid_slope.max():.1f}° | "
      f"Elevation: {grid_elev.min():.0f}–{grid_elev.max():.0f} m")


# ── 2. ESA WorldCover LULC ────────────────────────────────────────────────────
lulc_pts    = np.array([[p["lat"], p["lon"]] for p in lulc_raw])
lulc_cls_v  = np.array([p["lulc_class"] for p in lulc_raw])
lulc_name_v = np.array([p["lulc_name"]  for p in lulc_raw])
lulc_scr_v  = np.array([p["lulc_solar_score"] for p in lulc_raw])

grid_lulc_score, _ = nn_interp(lulc_pts, lulc_scr_v, grid_pts)
grid_lulc_cls, _   = nn_interp(lulc_pts, lulc_cls_v, grid_pts)
grid_lulc_idx, _   = nn_interp(lulc_pts, np.arange(len(lulc_name_v)), grid_pts)
grid_lulc_name     = lulc_name_v[grid_lulc_idx]
print(f"LULC scores: {np.unique(grid_lulc_score)}")


# ── 3. PVGIS GHI ─────────────────────────────────────────────────────────────
ghi_pts  = np.array([[p["lat"], p["lon"]] for p in ghi_raw])
ghi_yv   = np.array([p.get("GHI_y") or 0 for p in ghi_raw])   # kWh/m²/yr
ey_v     = np.array([p.get("E_y")   or 0 for p in ghi_raw])   # kWh/kWp/yr

grid_ghi, _ = nn_interp(ghi_pts, ghi_yv, grid_pts)
grid_ey,  _ = nn_interp(ghi_pts, ey_v,   grid_pts)

def ghi_score(g):
    if g >= 1980: return 4
    elif g >= 1965: return 3
    elif g >= 1950: return 2
    return 1

grid_ghi_score = np.array([ghi_score(g) for g in grid_ghi])
print(f"GHI: {grid_ghi.min():.0f}–{grid_ghi.max():.0f} kWh/m²/yr")


# ── 4. NASA POWER temperature ─────────────────────────────────────────────────
nasa_pts  = np.array([[p["lat"], p["lon"]] for p in nasa_raw])
nasa_ghid = np.array([p.get("GHI_kwh_m2_day") or 0 for p in nasa_raw])
nasa_t2m  = np.array([p.get("T2M_c")          or 0 for p in nasa_raw])

grid_nasa_ghi, _ = nn_interp(nasa_pts, nasa_ghid, grid_pts)
grid_t2m, _      = nn_interp(nasa_pts, nasa_t2m,  grid_pts)

def temp_score(t):
    if t <= 25: return 4
    elif t <= 26: return 3
    elif t <= 27: return 2
    return 1

grid_temp_score = np.array([temp_score(t) for t in grid_t2m])


# ── 5. OSM Power Lines distance ───────────────────────────────────────────────
pwr_nodes = []
for elem in pwr_raw:
    if elem.get("type") == "way" and "geometry" in elem:
        for n in elem["geometry"]:
            if "lat" in n and "lon" in n:
                pwr_nodes.append([n["lat"], n["lon"]])
    elif elem.get("type") == "node" and "lat" in elem:
        pwr_nodes.append([elem["lat"], elem["lon"]])

if pwr_nodes:
    pwr_tree = cKDTree(np.array(pwr_nodes))
    pwr_dists_km = pwr_tree.query(grid_pts)[0] * 111.0
else:
    pwr_dists_km = np.full(len(grid_pts), 50.0)
print(f"Power line dist: {pwr_dists_km.min():.2f}–{pwr_dists_km.max():.2f} km")

def power_score(d):
    if d <= 2: return 4
    elif d <= 5: return 3
    elif d <= 10: return 2
    return 1

grid_power_score = np.array([power_score(d) for d in pwr_dists_km])


# ── 6. OSM Road distance ─────────────────────────────────────────────────────
road_nodes = []
for elem in hwy_raw:
    if elem.get("type") == "way" and "geometry" in elem:
        for n in elem["geometry"]:
            if "lat" in n and "lon" in n:
                road_nodes.append([n["lat"], n["lon"]])

if road_nodes:
    road_tree = cKDTree(np.array(road_nodes))
    road_dists_km = road_tree.query(grid_pts)[0] * 111.0
else:
    road_dists_km = np.full(len(grid_pts), 30.0)
print(f"Road dist: {road_dists_km.min():.2f}–{road_dists_km.max():.2f} km")

def road_score(d):
    if d <= 1: return 4
    elif d <= 3: return 3
    elif d <= 8: return 2
    return 1

grid_road_score = np.array([road_score(d) for d in road_dists_km])


# ── Village assignment ────────────────────────────────────────────────────────
VILLAGE_ZONES = [
    ((11.95, 12.10, 78.63, 79.00), "Chinnasalem"),
    ((11.95, 12.10, 79.00, 79.33), "Sankarapuram"),
    ((11.80, 11.95, 78.63, 78.98), "Kallakurichi"),
    ((11.80, 11.95, 78.98, 79.33), "Ulundurpet"),
    ((11.65, 11.80, 78.63, 78.98), "Thirukoilur"),
    ((11.65, 11.80, 78.98, 79.33), "Rishivandiyam"),
    ((11.62, 11.65, 78.63, 79.10), "Vriddhachalam"),
    ((11.62, 11.65, 79.10, 79.33), "Pennadam"),
]

def get_village(lat, lon):
    for (la1, la2, lo1, lo2), v in VILLAGE_ZONES:
        if la1 <= lat <= la2 and lo1 <= lon <= lo2:
            return v
    return "Kallakurichi"


# ── Assemble final records ────────────────────────────────────────────────────
SOURCES = {
    "elevation": "NASA SRTM30m via OpenTopoData.org",
    "slope":     "Computed from SRTM via finite differences",
    "lulc":      "ESA WorldCover 2020 v100 via Terrascope WMS",
    "solar_pvgis": "PVGIS API v5.2 ERA5 — in-plane irradiation H(i)_y",
    "solar_nasa":  "NASA POWER v8 MERRA-2 — daily GHI climatology",
    "power":     "OpenStreetMap Overpass API — power lines/substations",
    "roads":     "OpenStreetMap Overpass API — primary/secondary highways",
}

records = []
for i in range(len(grid_pts)):
    lat, lon = grid_pts[i]
    records.append({
        "parcel_id":         f"KLK-{i+1:04d}",
        "village":           get_village(lat, lon),
        "lat":               round(float(lat), 5),
        "lon":               round(float(lon), 5),
        "elevation_m":       round(float(grid_elev[i]), 1),
        "slope_deg":         round(float(grid_slope[i]), 2),
        "slope_score":       int(grid_slope_score[i]),
        "lulc_class":        int(grid_lulc_cls[i]),
        "lulc_name":         str(grid_lulc_name[i]),
        "lulc_score":        int(grid_lulc_score[i]),
        "ghi_kwh_m2_yr":     round(float(grid_ghi[i]), 1),
        "pv_yield_kwh_kwp":  round(float(grid_ey[i]), 0),
        "ghi_score":         int(grid_ghi_score[i]),
        "ghi_daily":         round(float(grid_nasa_ghi[i]), 3),
        "temp_c":            round(float(grid_t2m[i]), 2),
        "temp_score":        int(grid_temp_score[i]),
        "power_dist_km":     round(float(pwr_dists_km[i]), 3),
        "power_score":       int(grid_power_score[i]),
        "road_dist_km":      round(float(road_dists_km[i]), 3),
        "road_score":        int(grid_road_score[i]),
        "sources":           SOURCES,
    })

df = pd.DataFrame(records)
print(f"\nFinal dataset: {len(df)} parcels")
print(df[["slope_score","lulc_score","ghi_score","power_score","road_score","temp_score"]].describe().round(2))

df.to_csv(os.path.join(PROC, "kallakurichi_parcels.csv"), index=False)
with open(os.path.join(PROC, "kallakurichi_parcels.json"), "w") as f:
    json.dump(records, f, indent=2)

print(f"\n✅ Saved → data/processed/kallakurichi_parcels.csv + .json")
