"""
04_fetch_esa_worldcover.py — Fetch ESA WorldCover LULC via WMS
==============================================================
Source  : ESA WorldCover 2020 v100 (10 m resolution)
          Served via Terrascope WMS: https://services.terrascope.be/wms/v2
          Layer: WORLDCOVER_2020_MAP  |  CRS: EPSG:3857

Method  : Sample each grid point with a 5×5 pixel WMS GetMap request.
          The centre-pixel RGB is decoded to ESA class code via colour lookup.
          Colour table: https://esa-worldcover.org/en/data-access

Output  : data/raw/esa_worldcover_lulc.json

Fields per point:
  lat, lon, lulc_class, lulc_name, lulc_solar_score, pixel_rgb, source

Note    : Script 07 later performs a full raster analysis via direct S3 tile
          access; this WMS sample is used for the parcel-grid scoring in
          script 05 and as a lightweight fallback.

Citation:
  Zanaga D. et al. (2022). ESA WorldCover 10 m 2021 v200.
  doi:10.5281/zenodo.7254221

Usage: python scripts/04_fetch_esa_worldcover.py
"""

import sys
import time
from io import BytesIO
from pathlib import Path

import numpy as np
import requests
from PIL import Image
from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    CITATIONS,
    ESA_LAT_MAX,
    ESA_LAT_MIN,
    ESA_LON_MAX,
    ESA_LON_MIN,
    ESA_N_LAT,
    ESA_N_LON,
    ESA_RGB_MAP,
    LULC_CLASSES,
    RAW_DIR,
)
from utils import get_logger, save_json

log = get_logger("04_fetch_esa")

WMS_URL   = "https://services.terrascope.be/wms/v2"
WMS_LAYER = "WORLDCOVER_2020_MAP"
REQUEST_INTERVAL = 0.10   # seconds — polite rate limit (~10 req/s)
MAX_RETRIES      = 3

# Coordinate transformer: WGS84 → Web Mercator (EPSG:3857)
_XFORM = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)


# ─── Helpers ────────────────────────────────────────────────────────────────────

def closest_esa_class(r: int, g: int, b: int, threshold: int = 80) -> int:
    """
    Return the ESA class code whose canonical RGB is closest to (r, g, b).
    Falls back to class 60 (Bare/sparse) if the nearest distance exceeds
    the threshold — this typically indicates NoData or ocean pixels.
    """
    best_cls, best_dist = 60, float("inf")
    for (cr, cg, cb), cls in ESA_RGB_MAP.items():
        dist = ((r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2) ** 0.5
        if dist < best_dist:
            best_dist, best_cls = dist, cls
    return best_cls if best_dist < threshold else 60


def sample_lulc(lat: float, lon: float, session: requests.Session,
                d_deg: float = 0.003) -> dict | None:
    """
    Sample ESA WorldCover class at (lat, lon) via a 5×5 px WMS GetMap request.
    d_deg controls the bounding-box half-width (~300 m at this latitude).
    """
    x1, y1 = _XFORM.transform(lon - d_deg, lat - d_deg)
    x2, y2 = _XFORM.transform(lon + d_deg, lat + d_deg)

    params = {
        "SERVICE": "WMS", "VERSION": "1.1.1", "REQUEST": "GetMap",
        "LAYERS":  WMS_LAYER, "SRS": "EPSG:3857",
        "BBOX":    f"{x1},{y1},{x2},{y2}",
        "WIDTH":   "5",  "HEIGHT": "5",
        "FORMAT":  "image/png", "STYLES": "",
    }
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(WMS_URL, params=params, timeout=20)
            if resp.status_code != 200 or b"PNG" not in resp.content[:10]:
                return None
            img = Image.open(BytesIO(resp.content)).convert("RGB")
            rgb = img.getpixel((2, 2))   # centre pixel (0-indexed)
            cls = closest_esa_class(*rgb[:3])
            name,  _, solar_score = LULC_CLASSES.get(cls, ("Unknown", "#999999", 2))
            return {
                "lat":             round(lat, 4),
                "lon":             round(lon, 4),
                "lulc_class":      cls,
                "lulc_name":       name,
                "lulc_solar_score": solar_score,
                "pixel_rgb":       list(rgb[:3]),
                "source":          "ESA WorldCover 2020 v100 via Terrascope WMS",
            }
        except Exception as exc:
            if attempt == MAX_RETRIES:
                log.debug(f"WMS ({lat:.4f},{lon:.4f}) failed: {exc}")
                return None
            time.sleep(0.5 * attempt)
    return None


# ─── Main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=" * 60)
    log.info("  Script 04 — ESA WorldCover 2020 LULC (WMS sampling)")
    log.info(f"  Grid: {ESA_N_LAT} × {ESA_N_LON} = {ESA_N_LAT * ESA_N_LON} points")
    log.info(f"  Area: [{ESA_LAT_MIN}–{ESA_LAT_MAX}°N, {ESA_LON_MIN}–{ESA_LON_MAX}°E]")
    log.info("=" * 60)

    lat_grid = np.linspace(ESA_LAT_MIN, ESA_LAT_MAX, ESA_N_LAT)
    lon_grid = np.linspace(ESA_LON_MIN, ESA_LON_MAX, ESA_N_LON)
    total    = len(lat_grid) * len(lon_grid)

    log.info(f"Sampling via Terrascope WMS (≈{total} requests, ~{total * REQUEST_INTERVAL:.0f} s)...")
    session = requests.Session()
    results: list[dict] = []
    errors  = 0

    for i, lat in enumerate(lat_grid):
        for lon in lon_grid:
            rec = sample_lulc(float(lat), float(lon), session)
            if rec:
                results.append(rec)
            else:
                errors += 1
            time.sleep(REQUEST_INTERVAL)

        # Progress every 3 rows
        if (i + 1) % 3 == 0 or (i + 1) == len(lat_grid):
            log.info(f"  Row {i+1}/{len(lat_grid)}  |  {len(results)} sampled  |  {errors} errors")

    # ── Class distribution summary ─────────────────────────────────────────────
    dist: dict[str, int] = {}
    for r in results:
        dist[r["lulc_name"]] = dist.get(r["lulc_name"], 0) + 1

    log.info("-" * 60)
    log.info(f"Total sampled : {len(results)} / {total}  (errors: {errors})")
    log.info("Class distribution (sorted by frequency):")
    for name, count in sorted(dist.items(), key=lambda x: -x[1]):
        pct = count / len(results) * 100 if results else 0
        log.info(f"  {name:<25s} {count:>5d}  ({pct:.1f}%)")

    # ── Save ───────────────────────────────────────────────────────────────────
    out_path = RAW_DIR / "esa_worldcover_lulc.json"
    save_json(
        {
            "points":    results,
            "n_points":  len(results),
            "grid":      f"{ESA_N_LAT} × {ESA_N_LON}",
            "bbox":      {
                "lat_min": ESA_LAT_MIN, "lat_max": ESA_LAT_MAX,
                "lon_min": ESA_LON_MIN, "lon_max": ESA_LON_MAX,
            },
            "source":    "ESA WorldCover 2020 v100 via Terrascope WMS (EPSG:3857)",
            "citation":  CITATIONS["esa_worldcover"],
        },
        out_path,
    )
    log.info(f"Saved → {out_path}")
    log.info("Run script 05 next: python scripts/05_process_data.py")


if __name__ == "__main__":
    main()
