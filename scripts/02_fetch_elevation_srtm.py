"""
Script 02 — Fetch SRTM Elevation Data
Source:  NASA SRTM 30m (1 arc-second) via OpenTopoData.org REST API
         https://www.opentopodata.org/datasets/srtm30m/
Output:  data/raw/srtm_elevation.json
         Columns: lat, lon, elevation_m, source

Resolution: OpenTopoData returns SRTM 30m (1 arc-sec ≈ 30m at equator)
Citation:   NASA SRTM, Farr et al. (2007), doi:10.1029/2005RG000183
"""

import requests, json, time, numpy as np, os

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
TOPO_URL = "https://api.opentopodata.org/v1/srtm30m"
BATCH_SIZE = 50

# Sampling grid over Kallakurichi district
LAT_MIN, LAT_MAX = 11.62, 12.08
LON_MIN, LON_MAX = 78.63, 79.33
N_LAT, N_LON = 12, 15  # 180 sample points


def fetch_elevation_batch(lat_lons: list[tuple]) -> list[dict]:
    locations_str = "|".join(f"{la:.4f},{lo:.4f}" for la, lo in lat_lons)
    r = requests.get(TOPO_URL, params={"locations": locations_str}, timeout=40)
    r.raise_for_status()
    data = r.json()
    results = []
    for (la, lo), res in zip(lat_lons, data.get("results", [])):
        results.append({
            "lat":         round(float(la), 4),
            "lon":         round(float(lo), 4),
            "elevation_m": res.get("elevation"),
            "source":      "SRTM30m via OpenTopoData.org",
        })
    return results


if __name__ == "__main__":
    lat_g = np.linspace(LAT_MIN, LAT_MAX, N_LAT)
    lon_g = np.linspace(LON_MIN, LON_MAX, N_LON)
    all_pts = [(float(la), float(lo)) for la in lat_g for lo in lon_g]
    print(f"Fetching SRTM elevation for {len(all_pts)} points in batches of {BATCH_SIZE}...")

    all_results = []
    for start in range(0, len(all_pts), BATCH_SIZE):
        batch = all_pts[start : start + BATCH_SIZE]
        try:
            res = fetch_elevation_batch(batch)
            all_results.extend(res)
            print(f"  {len(all_results)}/{len(all_pts)} done")
        except Exception as e:
            print(f"  ⚠️  Batch error: {e}")
        time.sleep(1.5)

    elevs = [r["elevation_m"] for r in all_results if r["elevation_m"] is not None]
    print(f"\n✅ {len(all_results)} points fetched")
    if elevs:
        print(f"Elevation range: {min(elevs):.0f} – {max(elevs):.0f} m")

    out_path = os.path.join(OUT_DIR, "srtm_elevation.json")
    with open(out_path, "w") as f:
        json.dump({"points": all_results, "source": "NASA SRTM30m via OpenTopoData.org",
                   "n_points": len(all_results)}, f, indent=2)
    print(f"Saved → {out_path}")
