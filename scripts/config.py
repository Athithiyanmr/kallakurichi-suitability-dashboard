"""
config.py — Shared configuration for the Kallakurichi Solar Suitability Pipeline
=================================================================================
All scripts import from here.  Edit this file to change the study area, grid
density, API endpoints, or scoring thresholds without touching individual scripts.
"""

from pathlib import Path

# ─── Project layout ─────────────────────────────────────────────────────────────
ROOT_DIR  = Path(__file__).resolve().parent.parent
RAW_DIR   = ROOT_DIR / "data" / "raw"
PROC_DIR  = ROOT_DIR / "data" / "processed"
OUT_DIR   = ROOT_DIR / "data" / "outputs"

for _d in (RAW_DIR, PROC_DIR, OUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ─── Study area — Kallakurichi District, Tamil Nadu ─────────────────────────────
DISTRICT  = "Kallakurichi"
STATE     = "Tamil Nadu"

# Bounding box  (south, west, north, east)
LAT_MIN   = 11.55
LAT_MAX   = 12.25
LON_MIN   = 78.55
LON_MAX   = 79.25

# Overpass-style  (S,W,N,E)
BBOX_OVERPASS = f"{LAT_MIN},{LON_MIN},{LAT_MAX},{LON_MAX}"

# Rasterio/GDAL  (W,S,E,N)
BBOX_RASTERIO = (LON_MIN, LAT_MIN, LON_MAX, LAT_MAX)

# ─── SRTM sampling grid (script 02) ─────────────────────────────────────────────
SRTM_N_LAT   = 12    # rows
SRTM_N_LON   = 15    # cols   → 180 points total
SRTM_LAT_MIN = 11.62
SRTM_LAT_MAX = 12.08
SRTM_LON_MIN = 78.63
SRTM_LON_MAX = 79.33

# ─── Solar data sampling grid (script 03) ───────────────────────────────────────
SOLAR_N_LAT   = 8
SOLAR_N_LON   = 10   # → 80 points total
SOLAR_LAT_MIN = 11.65
SOLAR_LAT_MAX = 12.05
SOLAR_LON_MIN = 78.65
SOLAR_LON_MAX = 79.30

# PV system assumptions (PVGIS)
PV_TILT_DEG    = 15    # Fixed tilt optimal for ~12°N latitude
PV_AZIMUTH_DEG = 0     # Due south (180° = due south in PVGIS convention → use 0)
PV_LOSS_PCT    = 14    # System losses (cable, inverter, soiling)
PV_TECH        = "crystSi"   # Crystalline silicon

# ─── ESA WorldCover WMS sampling grid (script 04) ───────────────────────────────
ESA_N_LAT   = 18
ESA_N_LON   = 22    # → 396 points total
ESA_LAT_MIN = 11.62
ESA_LAT_MAX = 12.08
ESA_LON_MIN = 78.63
ESA_LON_MAX = 79.33

# ─── Analysis grid (script 05) ──────────────────────────────────────────────────
GRID_N_LAT = 20
GRID_N_LON = 20    # → 400 parcels total

# ─── ESA WorldCover 2021 v200 — AWS S3 public tiles ─────────────────────────────
ESA_S3_TILES = [
    "https://esa-worldcover.s3.amazonaws.com/v200/2021/map/"
    "ESA_WorldCover_10m_2021_v200_N12E078_Map.tif",
    "https://esa-worldcover.s3.amazonaws.com/v200/2021/map/"
    "ESA_WorldCover_10m_2021_v200_N09E078_Map.tif",
]

# ─── OSM Overpass API ────────────────────────────────────────────────────────────
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
]
OVERPASS_TIMEOUT   = 90   # seconds per request
OVERPASS_RETRY_S   = 3    # seconds between mirror retries
HTTP_HEADERS = {
    "User-Agent": (
        "KallakurichiSolarPipeline/2.0 "
        "(https://github.com/Athithiyanmr/kallakurichi-suitability-dashboard) "
        "athithiyan@aurovilleconsulting.com"
    )
}

# ─── ESA WorldCover class definitions ───────────────────────────────────────────
# class_code → (display_name, hex_colour, solar_suitability_score_1_to_4)
LULC_CLASSES: dict[int, tuple[str, str, int]] = {
    10:  ("Tree cover",          "#006400", 2),
    20:  ("Shrubland",           "#FFBB22", 3),
    30:  ("Grassland",           "#FFFF4C", 3),
    40:  ("Cropland",            "#F096FF", 3),
    50:  ("Built-up",            "#FA0000", 1),
    60:  ("Bare/sparse veg",     "#B4B4B4", 4),   # Primary target
    70:  ("Snow/ice",            "#F0F0F0", 1),
    80:  ("Water bodies",        "#0064C8", 1),
    90:  ("Herbaceous wetland",  "#0096A0", 2),
    95:  ("Mangroves",           "#00CF75", 1),
    100: ("Moss/lichen",         "#FAE6A0", 4),
}
TARGET_LULC_CLASS = 60   # Bare/sparse vegetation — primary solar target

# ESA canonical RGB lookup (for WMS pixel decoding in script 04)
ESA_RGB_MAP: dict[tuple[int,int,int], int] = {
    (0,   100, 0):   10,
    (255, 187, 34):  20,
    (255, 255, 76):  30,
    (240, 150, 255): 40,
    (250, 0,   0):   50,
    (180, 180, 180): 60,
    (240, 240, 240): 70,
    (0,   100, 200): 80,
    (0,   150, 160): 90,
    (0,   207, 117): 95,
    (250, 230, 160): 100,
}

# ─── Suitability scoring thresholds ─────────────────────────────────────────────
# Each factor scored 1–4 (1 = least suitable, 4 = most suitable)

SLOPE_THRESHOLDS = [
    (3.0,  4),   # < 3°     → Very suitable
    (8.0,  3),   # 3–8°     → Suitable
    (15.0, 2),   # 8–15°    → Moderate
    (None, 1),   # > 15°    → Not suitable
]

GHI_THRESHOLDS = [
    (1980, 4),   # ≥ 1980   → Very suitable
    (1965, 3),   # 1965–80  → Suitable
    (1950, 2),   # 1950–65  → Moderate
    (None, 1),   # < 1950   → Not suitable
]

POWER_THRESHOLDS = [
    (2.0,  4),   # ≤ 2 km   → Very suitable
    (5.0,  3),   # 2–5 km
    (10.0, 2),   # 5–10 km
    (None, 1),   # > 10 km
]

ROAD_THRESHOLDS = [
    (1.0,  4),   # ≤ 1 km
    (3.0,  3),   # 1–3 km
    (8.0,  2),   # 3–8 km
    (None, 1),   # > 8 km
]

TEMP_THRESHOLDS = [
    (25.0, 4),   # ≤ 25°C   → Very suitable
    (26.0, 3),
    (27.0, 2),
    (None, 1),   # > 27°C
]

# Composite class labels
SUITABILITY_CLASSES = [
    (3.50, "Very High"),
    (2.75, "High"),
    (2.00, "Moderate"),
    (0.00, "Low"),
]

# ─── Village zone definitions (for parcel labelling in script 05) ────────────────
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

# ─── Data source citations ────────────────────────────────────────────────────────
CITATIONS = {
    "esa_worldcover": (
        "Zanaga D. et al. (2022). ESA WorldCover 10m 2021 v200. "
        "doi:10.5281/zenodo.7254221"
    ),
    "srtm": (
        "Farr T.G. et al. (2007). The Shuttle Radar Topography Mission. "
        "Rev. Geophys. doi:10.1029/2005RG000183"
    ),
    "pvgis": (
        "Huld T. et al. (2012). A new solar radiation database for estimating "
        "PV performance in Europe and Africa. Solar Energy. "
        "doi:10.1016/j.solener.2012.03.006"
    ),
    "nasa_power": (
        "Stackhouse P.W. et al. (2019). NASA POWER: Prediction of Worldwide "
        "Energy Resources. Bull. Amer. Meteor. Soc."
    ),
    "osm": "© OpenStreetMap contributors. Open Database Licence (ODbL) 1.0.",
}
