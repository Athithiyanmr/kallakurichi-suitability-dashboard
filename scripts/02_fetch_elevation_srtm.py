"""
02_fetch_elevation_srtm.py — Fetch SRTM Elevation Data
======================================================
Source  : NASA SRTM 30 m (1 arc-second) via OpenTopoData REST API
          https://www.opentopodata.org/datasets/srtm30m/
Output  : data/raw/srtm_elevation.json

Fields per point:
  lat, lon, elevation_m, source

Citation:
  Farr T.G. et al. (2007). The Shuttle Radar Topography Mission.
  Rev. Geophys., 45, RG2004. doi:10.1029/2005RG000183

Usage: python scripts/02_fetch_elevation_srtm.py
"""

import sys
import time
from pathlib import Path

import numpy as np
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    CITATIONS,
    RAW_DIR,
    SRTM_LAT_MAX,
    SRTM_LAT_MIN,
    SRTM_LON_MAX,
    SRTM_LON_MIN,
    SRTM_N_LAT,
    SRTM_N_LON,
)
from utils import get_logger, save_json

log = get_logger("02_fetch_srtm")

TOPO_URL   = "https://api.opentopodata.org/v1/srtm30m"
BATCH_SIZE = 50        # OpenTopoData max per request
RETRY_WAIT = 1.5       # seconds between batches
MAX_RETRIES = 3


# ─── Helpers ────────────────────────────────────────────────────────────────────

def fetch_elevation_batch(lat_lons: list[tuple[float, float]]) -> list[dict]:
    """Fetch SRTM elevation for a batch of (lat, lon) tuples."""
    locations_str = "|".join(f"{la:.4f},{lo:.4f}" for la, lo in lat_lons)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                TOPO_URL,
                params={"locations": locations_str},
                timeout=40,
            )
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as exc:
            log.warning(f"Batch attempt {attempt}/{MAX_RETRIES}: {exc}")
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_WAIT * attempt)

    results = []
    for (la, lo), res in zip(lat_lons, data.get("results", [])):
        results.append({
            "lat":         round(float(la), 4),
            "lon":         round(float(lo), 4),
            "elevation_m": res.get("elevation"),
            "source":      "NASA SRTM 30 m via OpenTopoData.org",
        })
    return results


# ─── Main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=" * 60)
    log.info("  Script 02 — SRTM 30 m Elevation")
    log.info(f"  Grid: {SRTM_N_LAT} × {SRTM_N_LON} = {SRTM_N_LAT * SRTM_N_LON} points")
    log.info(f"  Area: [{SRTM_LAT_MIN}–{SRTM_LAT_MAX}°N, {SRTM_LON_MIN}–{SRTM_LON_MAX}°E]")
    log.info("=" * 60)

    lat_grid = np.linspace(SRTM_LAT_MIN, SRTM_LAT_MAX, SRTM_N_LAT)
    lon_grid = np.linspace(SRTM_LON_MIN, SRTM_LON_MAX, SRTM_N_LON)
    all_pts: list[tuple[float, float]] = [
        (float(la), float(lo)) for la in lat_grid for lo in lon_grid
    ]

    log.info(f"Fetching elevation in batches of {BATCH_SIZE}...")
    all_results: list[dict] = []
    errors = 0

    for start in range(0, len(all_pts), BATCH_SIZE):
        batch = all_pts[start : start + BATCH_SIZE]
        try:
            results = fetch_elevation_batch(batch)
            all_results.extend(results)
            log.info(f"  {len(all_results)}/{len(all_pts)} points fetched")
        except Exception as exc:
            log.warning(f"  Batch [{start}:{start+BATCH_SIZE}] failed: {exc}")
            errors += len(batch)
        time.sleep(RETRY_WAIT)

    # ── Summary ────────────────────────────────────────────────────────────────
    elevations = [r["elevation_m"] for r in all_results if r.get("elevation_m") is not None]
    log.info("-" * 60)
    log.info(f"Points fetched : {len(all_results)}")
    log.info(f"Errors         : {errors}")
    if elevations:
        log.info(f"Elevation range: {min(elevations):.0f} – {max(elevations):.0f} m")
        log.info(f"Elevation mean : {sum(elevations)/len(elevations):.0f} m")

    # ── Save ───────────────────────────────────────────────────────────────────
    out_path = RAW_DIR / "srtm_elevation.json"
    save_json(
        {
            "points":      all_results,
            "n_points":    len(all_results),
            "grid":        f"{SRTM_N_LAT} × {SRTM_N_LON}",
            "bbox":        {
                "lat_min": SRTM_LAT_MIN, "lat_max": SRTM_LAT_MAX,
                "lon_min": SRTM_LON_MIN, "lon_max": SRTM_LON_MAX,
            },
            "source":      "NASA SRTM 30 m via OpenTopoData.org",
            "citation":    CITATIONS["srtm"],
        },
        out_path,
    )
    log.info(f"Saved → {out_path}")
    log.info("Run script 03 next: python scripts/03_fetch_solar_pvgis_nasa.py")


if __name__ == "__main__":
    main()
