"""
Script 04 — Fetch ESA WorldCover 2020 LULC
Source:  ESA WorldCover 2020 v100 (10m resolution)
         Served via Terrascope WMS — https://services.terrascope.be/wms/v2
         Layer: WORLDCOVER_2020_MAP
         CRS:   EPSG:3857 (required by this WMS endpoint)

Method:  Sample each grid point using a 5×5 pixel WMS GetMap request.
         The centre pixel RGB is decoded to ESA class code using colour lookup.
         ESA WorldCover colour table: https://esa-worldcover.org/en/data-access

Output:  data/raw/esa_worldcover_lulc.json
Citation: Zanaga et al. (2021), ESA WorldCover 10m 2020 v100.
          doi:10.5281/zenodo.5571936
"""

import requests, json, time, numpy as np, os
from PIL import Image
from io import BytesIO
from pyproj import Transformer

WMS_URL = "https://services.terrascope.be/wms/v2"
LAYER   = "WORLDCOVER_2020_MAP"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")

# Coordinate transformer: WGS84 → Web Mercator (required by WMS)
XFORM = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)

# ESA WorldCover colour table (RGB → class code)
ESA_COLORS: dict[tuple, int] = {
    (0, 100, 0):     10,   # Tree cover
    (255, 187, 34):  20,   # Shrubland
    (255, 255, 76):  30,   # Grassland
    (240, 150, 255): 40,   # Cropland
    (250, 0, 0):     50,   # Built-up
    (180, 180, 180): 60,   # Bare / sparse vegetation
    (240, 240, 240): 70,   # Snow and ice
    (0, 100, 200):   80,   # Permanent water bodies
    (0, 150, 160):   90,   # Herbaceous wetland
    (0, 207, 117):   95,   # Mangroves
    (250, 230, 160): 100,  # Moss and lichen
}
ESA_NAMES: dict[int, str] = {
    10: "Tree cover", 20: "Shrubland", 30: "Grassland",
    40: "Cropland", 50: "Built-up", 60: "Bare/sparse veg",
    70: "Snow/ice", 80: "Water bodies", 90: "Wetland",
    95: "Mangroves", 100: "Moss/lichen",
}

# Solar suitability score for each LULC class (1=low, 4=high)
LULC_SOLAR_SCORE: dict[int, int] = {
    10: 2,   # Tree cover — requires clearing, moderate concern
    20: 3,   # Shrubland — good, low conflict
    30: 3,   # Grassland — good, low conflict
    40: 3,   # Cropland — food security concern but commonly used for agri-solar
    50: 1,   # Built-up — not suitable for ground-mount
    60: 4,   # Bare/sparse — best, no conflict
    70: 1,   # Snow/ice — N/A for Tamil Nadu
    80: 1,   # Water bodies — floating solar possible but not scored here
    90: 2,   # Wetland — ecological sensitivity
    95: 1,   # Mangroves — legally protected
    100: 4,  # Moss/lichen — sparse, minimal conflict
}


def closest_esa_class(r: int, g: int, b: int, threshold: int = 80) -> int:
    best, best_dist = 60, 9999  # default: bare/sparse
    for (cr, cg, cb), cls in ESA_COLORS.items():
        d = ((r - cr)**2 + (g - cg)**2 + (b - cb)**2) ** 0.5
        if d < best_dist:
            best_dist, best = d, cls
    return best if best_dist < threshold else 60


def sample_lulc(lat: float, lon: float, d_deg: float = 0.003) -> dict | None:
    """Sample ESA WorldCover class for a single lat/lon coordinate."""
    x1, y1 = XFORM.transform(lon - d_deg, lat - d_deg)
    x2, y2 = XFORM.transform(lon + d_deg, lat + d_deg)
    params = {
        "SERVICE": "WMS", "VERSION": "1.1.1", "REQUEST": "GetMap",
        "LAYERS": LAYER, "SRS": "EPSG:3857",
        "BBOX": f"{x1},{y1},{x2},{y2}",
        "WIDTH": "5", "HEIGHT": "5",
        "FORMAT": "image/png", "STYLES": "",
    }
    r = requests.get(WMS_URL, params=params, timeout=20)
    if r.status_code != 200 or b'PNG' not in r.content[:10]:
        return None
    img = Image.open(BytesIO(r.content)).convert("RGB")
    rgb = img.getpixel((2, 2))  # centre pixel
    cls = closest_esa_class(*rgb[:3])
    return {
        "lat":   round(lat, 4),
        "lon":   round(lon, 4),
        "lulc_class":       cls,
        "lulc_name":        ESA_NAMES.get(cls, "Unknown"),
        "lulc_solar_score": LULC_SOLAR_SCORE.get(cls, 2),
        "pixel_rgb":        list(rgb[:3]),
        "source": "ESA WorldCover 2020 v100 via Terrascope WMS",
    }


if __name__ == "__main__":
    lat_g = np.linspace(11.62, 12.08, 18)
    lon_g = np.linspace(78.63, 79.33, 22)
    total = len(lat_g) * len(lon_g)
    print(f"Sampling ESA WorldCover LULC for {total} grid points...")

    results, errors = [], 0
    for i, lat in enumerate(lat_g):
        for lon in lon_g:
            rec = sample_lulc(float(lat), float(lon))
            if rec:
                results.append(rec)
            else:
                errors += 1
            time.sleep(0.08)
        if (i + 1) % 3 == 0:
            print(f"  {len(results)}/{total} sampled, {errors} errors")

    cls_dist: dict[str, int] = {}
    for r in results:
        n = r["lulc_name"]
        cls_dist[n] = cls_dist.get(n, 0) + 1
    print(f"\n✅ {len(results)} LULC points, {errors} errors")
    print("Class distribution:", dict(sorted(cls_dist.items(), key=lambda x: -x[1])))

    out_path = os.path.join(OUT_DIR, "esa_worldcover_lulc.json")
    with open(out_path, "w") as f:
        json.dump({
            "points": results,
            "source": "ESA WorldCover 2020 v100 via Terrascope WMS (EPSG:3857)",
            "n_points": len(results),
            "citation": "Zanaga et al. (2021) doi:10.5281/zenodo.5571936",
        }, f, indent=2)
    print(f"Saved → {out_path}")
