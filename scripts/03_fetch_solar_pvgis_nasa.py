"""
03_fetch_solar_pvgis_nasa.py — Fetch Solar Radiation Data
=========================================================
Sources :
  A) PVGIS API v5.2 (ERA5 database)
     https://re.jrc.ec.europa.eu/pvg_tools/en/tools.html
     → Annual PV yield (E_y kWh/kWp/yr), in-plane irradiation H(i)_y kWh/m²/yr

  B) NASA POWER v8 Climatology (MERRA-2)
     https://power.larc.nasa.gov/api/
     → Daily GHI, DNI, mean air temperature 2 m, wind speed 10 m

Outputs : data/raw/pvgis_ghi.json
          data/raw/nasa_power_ghi.json

Citation:
  Huld T. et al. (2012). Solar Energy doi:10.1016/j.solener.2012.03.006
  Stackhouse P.W. et al. (2019). NASA POWER. Bull. Amer. Meteor. Soc.

Usage: python scripts/03_fetch_solar_pvgis_nasa.py
"""

import sys
import time
from pathlib import Path

import numpy as np
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    CITATIONS,
    PV_AZIMUTH_DEG,
    PV_LOSS_PCT,
    PV_TECH,
    PV_TILT_DEG,
    RAW_DIR,
    SOLAR_LAT_MAX,
    SOLAR_LAT_MIN,
    SOLAR_LON_MAX,
    SOLAR_LON_MIN,
    SOLAR_N_LAT,
    SOLAR_N_LON,
)
from utils import get_logger, save_json

log = get_logger("03_fetch_solar")

PVGIS_URL   = "https://re.jrc.ec.europa.eu/api/v5_2/PVcalc"
NASA_URL    = "https://power.larc.nasa.gov/api/temporal/climatology/point"
RETRY_WAIT  = 0.6    # seconds between individual point requests
MAX_RETRIES = 3


# ─── PVGIS fetch ─────────────────────────────────────────────────────────────────

def fetch_pvgis(lat: float, lon: float) -> dict | None:
    """
    Fetch PVGIS PVcalc endpoint for a single (lat, lon) point.
    Returns annual PV yield (kWh/kWp/yr) and in-plane irradiation (kWh/m²/yr)
    using ERA5 dataset, crystalline silicon, fixed tilt as per config.
    """
    params = {
        "lat":          lat,
        "lon":          lon,
        "peakpower":    1,
        "loss":         PV_LOSS_PCT,
        "outputformat": "json",
        "pvtechchoice": PV_TECH,
        "mountingplace": "free",
        "angle":        PV_TILT_DEG,
        "aspect":       PV_AZIMUTH_DEG,
    }
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(PVGIS_URL, params=params, timeout=30)
            resp.raise_for_status()
            d    = resp.json()
            tot  = d.get("outputs", {}).get("totals", {}).get("fixed", {})
            meta = d.get("inputs", {})
            return {
                "lat":            lat,
                "lon":            lon,
                "E_y":            tot.get("E_y"),        # kWh/kWp/yr
                "ghi_kwh_m2_yr":  tot.get("H(i)_y"),    # kWh/m²/yr
                "E_d":            tot.get("E_d"),        # kWh/kWp/day (daily avg)
                "l_total":        tot.get("l_total"),    # % total system losses
                "pv_yield_kwh_kwp": tot.get("E_y"),     # alias for script 05 compat.
                "elevation_m":    meta.get("location", {}).get("elevation"),
                "database":       meta.get("meteo_data", {}).get("radiation_db", "PVGIS-ERA5"),
                "source":         "PVGIS API v5.2 ERA5",
            }
        except Exception as exc:
            if attempt == MAX_RETRIES:
                log.warning(f"PVGIS ({lat},{lon}) failed after {MAX_RETRIES} attempts: {exc}")
                return None
            time.sleep(RETRY_WAIT * attempt)


# ─── NASA POWER fetch ─────────────────────────────────────────────────────────────

def fetch_nasa_power(lat: float, lon: float) -> dict | None:
    """
    Fetch NASA POWER Climatology API for a single (lat, lon) point.
    Returns long-term annual averages (MERRA-2) for GHI, DNI, T2M, WS10M.
    """
    params = {
        "parameters": "ALLSKY_SFC_SW_DWN,ALLSKY_SFC_SW_DNI,T2M,WS10M",
        "community":  "RE",
        "longitude":  lon,
        "latitude":   lat,
        "format":     "JSON",
    }
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(NASA_URL, params=params, timeout=30)
            resp.raise_for_status()
            d    = resp.json()
            prop = d.get("properties", {}).get("parameter", {})
            return {
                "lat":              lat,
                "lon":              lon,
                "GHI_kwh_m2_day":  prop.get("ALLSKY_SFC_SW_DWN", {}).get("ANN"),
                "DNI_kwh_m2_day":  prop.get("ALLSKY_SFC_SW_DNI", {}).get("ANN"),
                "temp_c":          prop.get("T2M",    {}).get("ANN"),   # °C
                "wind_ms":         prop.get("WS10M",  {}).get("ANN"),   # m/s
                "source":          "NASA POWER v8 MERRA-2 climatology",
            }
        except Exception as exc:
            if attempt == MAX_RETRIES:
                log.warning(f"NASA POWER ({lat},{lon}) failed after {MAX_RETRIES} attempts: {exc}")
                return None
            time.sleep(RETRY_WAIT * attempt)


# ─── Main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=" * 60)
    log.info("  Script 03 — Solar Radiation (PVGIS + NASA POWER)")
    log.info(f"  Grid: {SOLAR_N_LAT} × {SOLAR_N_LON} = {SOLAR_N_LAT * SOLAR_N_LON} points")
    log.info(f"  PV config: tilt={PV_TILT_DEG}°, azimuth={PV_AZIMUTH_DEG}°, loss={PV_LOSS_PCT}%, tech={PV_TECH}")
    log.info("=" * 60)

    lat_grid = np.linspace(SOLAR_LAT_MIN, SOLAR_LAT_MAX, SOLAR_N_LAT)
    lon_grid = np.linspace(SOLAR_LON_MIN, SOLAR_LON_MAX, SOLAR_N_LON)
    pts = [
        (round(float(la), 4), round(float(lo), 4))
        for la in lat_grid for lo in lon_grid
    ]
    total = len(pts)

    pvgis_results: list[dict] = []
    nasa_results:  list[dict] = []

    log.info(f"Fetching PVGIS + NASA POWER for {total} points...")
    for i, (lat, lon) in enumerate(pts, 1):
        pvgis = fetch_pvgis(lat, lon)
        if pvgis:
            pvgis_results.append(pvgis)

        nasa = fetch_nasa_power(lat, lon)
        if nasa:
            nasa_results.append(nasa)

        time.sleep(RETRY_WAIT)
        if i % 10 == 0 or i == total:
            log.info(f"  {i}/{total} — PVGIS OK: {len(pvgis_results)}  NASA OK: {len(nasa_results)}")

    # ── PVGIS summary ──────────────────────────────────────────────────────────
    ghis = [r["ghi_kwh_m2_yr"] for r in pvgis_results if r.get("ghi_kwh_m2_yr")]
    eysv = [r["E_y"]           for r in pvgis_results if r.get("E_y")]
    log.info("-" * 60)
    if ghis:
        log.info(f"PVGIS GHI range   : {min(ghis):.1f} – {max(ghis):.1f} kWh/m²/yr")
        log.info(f"PVGIS GHI mean    : {sum(ghis)/len(ghis):.1f} kWh/m²/yr")
    if eysv:
        log.info(f"PVGIS PV yield    : {min(eysv):.0f} – {max(eysv):.0f} kWh/kWp/yr")

    nasa_ghis = [r["GHI_kwh_m2_day"] for r in nasa_results if r.get("GHI_kwh_m2_day")]
    if nasa_ghis:
        log.info(f"NASA POWER GHI    : {min(nasa_ghis):.3f} – {max(nasa_ghis):.3f} kWh/m²/day")

    # ── Save ───────────────────────────────────────────────────────────────────
    pvgis_path = RAW_DIR / "pvgis_ghi.json"
    save_json(
        {
            "points":      pvgis_results,
            "n_points":    len(pvgis_results),
            "grid":        f"{SOLAR_N_LAT} × {SOLAR_N_LON}",
            "pv_config":   {
                "tilt_deg": PV_TILT_DEG, "azimuth_deg": PV_AZIMUTH_DEG,
                "loss_pct": PV_LOSS_PCT, "technology":  PV_TECH,
            },
            "source":      "PVGIS API v5.2 ERA5",
            "citation":    CITATIONS["pvgis"],
        },
        pvgis_path,
    )
    log.info(f"Saved → {pvgis_path}")

    nasa_path = RAW_DIR / "nasa_power_ghi.json"
    save_json(
        {
            "points":   nasa_results,
            "n_points": len(nasa_results),
            "source":   "NASA POWER v8 MERRA-2 climatology",
            "citation": CITATIONS["nasa_power"],
        },
        nasa_path,
    )
    log.info(f"Saved → {nasa_path}")
    log.info("Run script 04 next: python scripts/04_fetch_esa_worldcover.py")


if __name__ == "__main__":
    main()
