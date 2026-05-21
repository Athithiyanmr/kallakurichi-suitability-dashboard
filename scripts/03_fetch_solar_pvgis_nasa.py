"""
Script 03 — Fetch Solar Radiation Data
Sources:
  A) PVGIS API v5.2 (ERA5 database)
     https://re.jrc.ec.europa.eu/pvg_tools/en/tools.html
     Parameters: Annual PV yield (E_y kWh/kWp/yr), In-plane irradiation H(i)_y kWh/m²/yr
  B) NASA POWER v8 Climatology (MERRA-2)
     https://power.larc.nasa.gov/api/
     Parameters: Daily GHI, DNI, mean temperature 2m, wind speed 10m

Output: data/raw/pvgis_ghi.json, data/raw/nasa_power_ghi.json
"""

import requests, json, time, numpy as np, os

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
os.makedirs(OUT_DIR, exist_ok=True)

LAT_MIN, LAT_MAX = 11.65, 12.05
LON_MIN, LON_MAX = 78.65, 79.30
N_LAT, N_LON = 8, 10  # 80 points


def fetch_pvgis(lat: float, lon: float) -> dict | None:
    """
    PVGIS PVcalc endpoint.
    Returns annual PV yield (kWh/kWp/yr) and in-plane irradiation (kWh/m²/yr).
    Dataset: ERA5 (global, covers India well at 0.28° resolution)
    Tilt: 15° fixed (near-optimal for Tamil Nadu latitude ~11-12°N)
    """
    params = {
        "lat": lat, "lon": lon,
        "peakpower": 1, "loss": 14,
        "outputformat": "json",
        "pvtechchoice": "crystSi",   # Crystalline silicon (most common)
        "mountingplace": "free",     # Free-standing, best cooling
        "angle": 15,                 # Fixed tilt optimal for ~12°N
        "aspect": 0,                 # Due south
    }
    r = requests.get("https://re.jrc.ec.europa.eu/api/v5_2/PVcalc", params=params, timeout=30)
    r.raise_for_status()
    d = r.json()
    tot  = d.get("outputs", {}).get("totals", {}).get("fixed", {})
    meta = d.get("inputs", {})
    return {
        "lat": lat, "lon": lon,
        "E_y":      tot.get("E_y"),          # kWh/kWp/yr — annual PV yield
        "GHI_y":    tot.get("H(i)_y"),       # kWh/m²/yr — annual in-plane irradiation
        "E_d":      tot.get("E_d"),           # kWh/kWp/day — daily average
        "l_total":  tot.get("l_total"),       # % total system losses
        "elev":     meta.get("location", {}).get("elevation"),
        "db":       meta.get("meteo_data", {}).get("radiation_db", "PVGIS-ERA5"),
        "source":   "PVGIS API v5.2 ERA5",
    }


def fetch_nasa_power(lat: float, lon: float) -> dict | None:
    """
    NASA POWER Climatology API.
    Returns long-term average (MERRA-2 model) for key RE parameters.
    """
    params = {
        "parameters": "ALLSKY_SFC_SW_DWN,ALLSKY_SFC_SW_DNI,T2M,WS10M",
        "community": "RE",
        "longitude": lon, "latitude": lat,
        "format": "JSON",
    }
    r = requests.get("https://power.larc.nasa.gov/api/temporal/climatology/point",
                     params=params, timeout=30)
    r.raise_for_status()
    d    = r.json()
    prop = d.get("properties", {}).get("parameter", {})
    return {
        "lat": lat, "lon": lon,
        "GHI_kwh_m2_day": prop.get("ALLSKY_SFC_SW_DWN", {}).get("ANN"),
        "DNI_kwh_m2_day": prop.get("ALLSKY_SFC_SW_DNI", {}).get("ANN"),
        "T2M_c":          prop.get("T2M", {}).get("ANN"),
        "WS10M_ms":       prop.get("WS10M", {}).get("ANN"),
        "source": "NASA POWER v8 MERRA-2 climatology",
    }


if __name__ == "__main__":
    lat_g = np.linspace(LAT_MIN, LAT_MAX, N_LAT)
    lon_g = np.linspace(LON_MIN, LON_MAX, N_LON)
    pts   = [(round(float(la), 4), round(float(lo), 4)) for la in lat_g for lo in lon_g]
    print(f"Fetching solar data for {len(pts)} grid points...")

    pvgis_results, nasa_results = [], []
    for i, (lat, lon) in enumerate(pts):
        try:
            pvgis_results.append(fetch_pvgis(lat, lon))
        except Exception as e:
            print(f"  PVGIS err ({lat},{lon}): {e}")
        try:
            nasa_results.append(fetch_nasa_power(lat, lon))
        except Exception as e:
            print(f"  NASA err ({lat},{lon}): {e}")
        time.sleep(0.5)
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(pts)} done")

    # PVGIS summary
    ghis = [r["GHI_y"] for r in pvgis_results if r.get("GHI_y")]
    eysv = [r["E_y"]   for r in pvgis_results if r.get("E_y")]
    if ghis:
        print(f"\nPVGIS GHI: {min(ghis):.1f} – {max(ghis):.1f} kWh/m²/yr")
        print(f"PVGIS PV yield: {min(eysv):.0f} – {max(eysv):.0f} kWh/kWp/yr")

    with open(os.path.join(OUT_DIR, "pvgis_ghi.json"), "w") as f:
        json.dump({"points": pvgis_results, "source": "PVGIS API v5.2 ERA5",
                   "n_points": len(pvgis_results),
                   "tilt_deg": 15, "azimuth_deg": 0, "loss_pct": 14}, f, indent=2)

    nasa_ghis = [r["GHI_kwh_m2_day"] for r in nasa_results if r.get("GHI_kwh_m2_day")]
    if nasa_ghis:
        print(f"NASA POWER GHI: {min(nasa_ghis):.3f} – {max(nasa_ghis):.3f} kWh/m²/day")

    with open(os.path.join(OUT_DIR, "nasa_power_ghi.json"), "w") as f:
        json.dump({"points": nasa_results, "source": "NASA POWER v8 MERRA-2",
                   "n_points": len(nasa_results)}, f, indent=2)

    print(f"\n✅ Saved PVGIS ({len(pvgis_results)} pts) and NASA POWER ({len(nasa_results)} pts)")
