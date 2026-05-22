"""
01_fetch_osm_data.py — Fetch OSM Infrastructure Data
=====================================================
Sources : OpenStreetMap via Overpass API
Fetches : Power lines, substations, towers, highways
Outputs : data/raw/osm_power.json
          data/raw/osm_highways.json

Run this script first.  It must succeed before scripts 02–07 can be run.
Usage   : python scripts/01_fetch_osm_data.py
"""

import sys
import time
from pathlib import Path

# Allow running from repo root OR from scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    BBOX_OVERPASS,
    HTTP_HEADERS,
    OVERPASS_MIRRORS,
    OVERPASS_RETRY_S,
    OVERPASS_TIMEOUT,
    RAW_DIR,
)
from utils import get_logger, overpass_fetch, save_json

log = get_logger("01_fetch_osm")


# ─── Overpass QL queries ─────────────────────────────────────────────────────────

POWER_QUERY = f"""
[out:json][timeout:{OVERPASS_TIMEOUT}];
(
  way["power"~"^(line|minor_line)$"]({BBOX_OVERPASS});
  node["power"="substation"]({BBOX_OVERPASS});
  node["power"="tower"]({BBOX_OVERPASS});
  way["power"="substation"]({BBOX_OVERPASS});
);
out body geom;
"""

HIGHWAY_QUERY = f"""
[out:json][timeout:{OVERPASS_TIMEOUT}];
(
  way["highway"~"^(motorway|trunk|primary|secondary|tertiary)$"]({BBOX_OVERPASS});
);
out body geom;
"""


# ─── Main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=" * 60)
    log.info("  Script 01 — OSM Power Infrastructure + Highways")
    log.info(f"  Bounding box: {BBOX_OVERPASS}")
    log.info("=" * 60)

    # ── Power infrastructure ───────────────────────────────────────────────────
    log.info("Fetching OSM power infrastructure (lines, substations, towers)...")
    power_data = overpass_fetch(
        query    = POWER_QUERY,
        label    = "power",
        out_path = RAW_DIR / "osm_power.json",
        logger   = log,
    )
    if power_data is None:
        log.error("Power data fetch failed after all mirrors.  Aborting.")
        sys.exit(1)

    n_subs = sum(
        1 for e in power_data.get("elements", [])
        if e.get("type") == "node" and e.get("tags", {}).get("power") == "substation"
    )
    log.info(f"  Substations found: {n_subs}")
    time.sleep(5)   # respectful pause between Overpass requests

    # ── Highways ───────────────────────────────────────────────────────────────
    log.info("Fetching OSM highway network (motorway → tertiary)...")
    highway_data = overpass_fetch(
        query    = HIGHWAY_QUERY,
        label    = "highways",
        out_path = RAW_DIR / "osm_highways.json",
        logger   = log,
    )
    if highway_data is None:
        log.error("Highway data fetch failed after all mirrors.  Aborting.")
        sys.exit(1)

    # ── Completion report ──────────────────────────────────────────────────────
    log.info("-" * 60)
    log.info("Script 01 complete.")
    log.info(f"  data/raw/osm_power.json    — {len(power_data.get('elements', [])):,} elements")
    log.info(f"  data/raw/osm_highways.json — {len(highway_data.get('elements', [])):,} elements")
    log.info("Run script 02 next: python scripts/02_fetch_elevation_srtm.py")


if __name__ == "__main__":
    main()
