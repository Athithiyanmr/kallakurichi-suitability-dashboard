"""
Script 01 — Fetch OSM Infrastructure Data
Sources: OpenStreetMap via Overpass API
Fetches: Power lines, substations, towers, highways
Output:  data/raw/osm_power.json, data/raw/osm_highways.json
"""

import requests, json, time, os, sys

# Kallakurichi district bounding box (south,west,north,east for Overpass)
BBOX = "11.60,78.60,12.10,79.35"

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
]

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
os.makedirs(OUT_DIR, exist_ok=True)

HEADERS = {"User-Agent": "KallakurichiSuitabilityDashboard/1.0 athithiyan@aurovilleconsulting.com"}


def overpass_fetch(query: str, label: str, out_path: str) -> dict | None:
    """Fetch from Overpass, trying mirrors on failure."""
    for url in OVERPASS_MIRRORS:
        try:
            r = requests.post(url, data={"data": query}, headers=HEADERS, timeout=90)
            if r.status_code == 200 and r.text.strip():
                data = r.json()
                with open(out_path, "w") as f:
                    json.dump(data, f)
                n = len(data.get("elements", []))
                print(f"  ✅ [{label}] {n} elements saved → {os.path.basename(out_path)}")
                return data
        except Exception as e:
            print(f"  ⚠️  Mirror {url}: {e}")
        time.sleep(3)
    print(f"  ❌ [{label}] all mirrors failed")
    return None


POWER_QUERY = f"""
[out:json][timeout:90];
(
  way["power"~"^(line|minor_line)$"]({BBOX});
  node["power"="substation"]({BBOX});
  node["power"="tower"]({BBOX});
  way["power"="substation"]({BBOX});
);
out body geom;
"""

HIGHWAY_QUERY = f"""
[out:json][timeout:90];
(
  way["highway"~"^(motorway|trunk|primary|secondary|tertiary)$"]({BBOX});
);
out body geom;
"""

if __name__ == "__main__":
    print("=== Fetching OSM Power Infrastructure ===")
    overpass_fetch(POWER_QUERY, "power", os.path.join(OUT_DIR, "osm_power.json"))
    time.sleep(5)

    print("\n=== Fetching OSM Highways ===")
    overpass_fetch(HIGHWAY_QUERY, "highways", os.path.join(OUT_DIR, "osm_highways.json"))

    print("\nDone. Run script 02 next.")
