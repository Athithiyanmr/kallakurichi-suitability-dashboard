"""
utils.py — Shared utility functions for the Kallakurichi Solar Suitability Pipeline
=====================================================================================
All scripts import from here to avoid code duplication.
"""

from __future__ import annotations

import json
import logging
import math
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from config import (
    GHI_THRESHOLDS,
    HTTP_HEADERS,
    LULC_CLASSES,
    OVERPASS_MIRRORS,
    OVERPASS_RETRY_S,
    OVERPASS_TIMEOUT,
    POWER_THRESHOLDS,
    ROAD_THRESHOLDS,
    SLOPE_THRESHOLDS,
    SUITABILITY_CLASSES,
    TEMP_THRESHOLDS,
    VILLAGE_ZONES,
)


# ─── Logging ─────────────────────────────────────────────────────────────────────

def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a stdout logger with consistent formatting."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s",
                          datefmt="%H:%M:%S")
    )
    logger.addHandler(handler)
    logger.setLevel(level)
    return logger


# ─── I/O helpers ─────────────────────────────────────────────────────────────────

def load_json(path: Path) -> Any:
    """Load a JSON file; raise FileNotFoundError with a helpful message."""
    if not path.exists():
        raise FileNotFoundError(
            f"Raw data file not found: {path}\n"
            f"Run the corresponding fetch script first."
        )
    with open(path) as f:
        return json.load(f)


def save_json(data: Any, path: Path, indent: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=indent)


# ─── Geo helpers ─────────────────────────────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres between two (lat, lon) points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def pixel_area_ha(transform, lat: float) -> float:
    """
    Area in hectares of one raster pixel at a given latitude.
    Works for geographic CRS rasters (degrees per pixel).
    """
    res_deg = abs(transform.a)   # degrees/pixel in x direction
    lon_m   = res_deg * math.cos(math.radians(lat)) * 111_320
    lat_m   = abs(transform.e) * 111_320
    return (lon_m * lat_m) / 10_000


# ─── Scoring functions ────────────────────────────────────────────────────────────

def _threshold_score(value: float, thresholds: list[tuple]) -> int:
    """
    Generic threshold scorer.
    thresholds: list of (upper_bound, score) sorted ascending by upper_bound.
    The last entry must have upper_bound=None (catch-all).
    """
    for upper, score in thresholds:
        if upper is None or value <= upper:
            return score
    return 1


def score_slope(deg: float)  -> int: return _threshold_score(deg,  SLOPE_THRESHOLDS)
def score_ghi(kwh: float)    -> int: return _threshold_score(kwh,  GHI_THRESHOLDS)
def score_power(km: float)   -> int: return _threshold_score(km,   POWER_THRESHOLDS)
def score_road(km: float)    -> int: return _threshold_score(km,   ROAD_THRESHOLDS)
def score_temp(c: float)     -> int: return _threshold_score(c,    TEMP_THRESHOLDS)


def score_lulc(lulc_class: int) -> int:
    return LULC_CLASSES.get(lulc_class, (None, None, 2))[2]


def composite_score(scores: dict[str, int], weights: dict[str, float]) -> float:
    """
    Weighted average of factor scores.
    scores:  {factor: score_1_to_4}
    weights: {factor: weight_float}  — need not sum to 1, normalised internally.
    """
    total_w = sum(weights[k] for k in scores if k in weights)
    if total_w == 0:
        return 0.0
    return sum(scores[k] * weights.get(k, 0) for k in scores) / total_w


def suitability_class(score: float) -> str:
    for threshold, label in SUITABILITY_CLASSES:
        if score >= threshold:
            return label
    return "Low"


# ─── OSM helpers ─────────────────────────────────────────────────────────────────

def extract_osm_nodes(osm_json: dict) -> list[dict]:
    """
    Extract unique lat/lon positions from an OSM Overpass response.
    Returns a deduplicated list of {"lat": ..., "lon": ...} dicts.
    """
    node_coords: dict[int, tuple[float, float]] = {}
    for e in osm_json.get("elements", []):
        if e.get("type") == "node" and "lat" in e:
            node_coords[e["id"]] = (e["lat"], e["lon"])

    seen: set[tuple[float, float]] = set()
    positions: list[dict] = []

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


def min_dist_km(lat: float, lon: float, nodes: list[dict]) -> float:
    """
    Minimum haversine distance (km) from (lat, lon) to any node in the list.
    Uses a cheap Euclidean pre-filter to skip far-away nodes.
    """
    best = float("inf")
    for n in nodes:
        approx = math.sqrt((n["lat"] - lat) ** 2 + (n["lon"] - lon) ** 2) * 111.0
        if approx < best * 1.5:
            d = haversine_km(lat, lon, n["lat"], n["lon"])
            if d < best:
                best = d
    return round(best, 3)


# ─── Overpass API ────────────────────────────────────────────────────────────────

def overpass_fetch(query: str, label: str, out_path: Path,
                   logger: logging.Logger | None = None) -> dict | None:
    """
    POST an Overpass QL query, trying mirrors in order on failure.
    Saves the result to out_path and returns the parsed JSON.
    """
    import requests

    log = logger or get_logger("overpass")
    for mirror in OVERPASS_MIRRORS:
        try:
            resp = requests.post(
                mirror,
                data={"data": query},
                headers=HTTP_HEADERS,
                timeout=OVERPASS_TIMEOUT,
            )
            if resp.status_code == 200 and resp.text.strip():
                data = resp.json()
                save_json(data, out_path)
                n = len(data.get("elements", []))
                log.info(f"[{label}] {n:,} elements  →  {out_path.name}")
                return data
            log.warning(f"[{label}] HTTP {resp.status_code} from {mirror}")
        except Exception as exc:
            log.warning(f"[{label}] {mirror}: {exc}")
        time.sleep(OVERPASS_RETRY_S)

    log.error(f"[{label}] All Overpass mirrors failed.")
    return None


# ─── Village lookup ───────────────────────────────────────────────────────────────

def get_village(lat: float, lon: float) -> str:
    for (la1, la2, lo1, lo2), name in VILLAGE_ZONES:
        if la1 <= lat <= la2 and lo1 <= lon <= lo2:
            return name
    return "Kallakurichi"


# ─── KD-tree nearest-neighbour ────────────────────────────────────────────────────

def nn_interp(src_pts: np.ndarray, src_vals: np.ndarray,
              query_pts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Nearest-neighbour interpolation using scipy KD-tree.
    Returns (interpolated_values, distances).
    """
    from scipy.spatial import cKDTree
    tree = cKDTree(src_pts)
    dists, idxs = tree.query(query_pts)
    return src_vals[idxs], dists


def build_osm_kdtree(osm_json: dict):
    """Build a scipy KD-tree from OSM element geometry nodes."""
    from scipy.spatial import cKDTree

    nodes: list[list[float]] = []
    node_coords: dict[int, tuple[float, float]] = {}

    for e in osm_json.get("elements", []):
        if e.get("type") == "node" and "lat" in e:
            node_coords[e["id"]] = (e["lat"], e["lon"])
            nodes.append([e["lat"], e["lon"]])
        elif e.get("type") == "way":
            for n in e.get("geometry", []):
                if "lat" in n:
                    nodes.append([n["lat"], n["lon"]])

    if not nodes:
        return None
    return cKDTree(np.array(nodes))
