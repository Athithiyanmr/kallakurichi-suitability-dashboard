# ☀️ Kallakurichi Land Suitability Dashboard

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://streamlit.io)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

Interactive geospatial dashboard for **solar energy land suitability analysis** in Kallakurichi District, Tamil Nadu, India. Built with real open-access data from NASA, ESA, PVGIS, and OpenStreetMap.

---

## 🗂️ Project Structure

```
kallakurichi-suitability-dashboard/
├── app.py                          # Streamlit dashboard application
├── requirements.txt                # Python dependencies
├── scripts/
│   ├── 01_fetch_osm_data.py        # OSM power lines + highways via Overpass API
│   ├── 02_fetch_elevation_srtm.py  # NASA SRTM30m elevation via OpenTopoData
│   ├── 03_fetch_solar_pvgis_nasa.py# PVGIS ERA5 + NASA POWER solar data
│   ├── 04_fetch_esa_worldcover.py  # ESA WorldCover 2020 LULC via WMS
│   └── 05_process_data.py          # Data processing + scoring pipeline
├── data/
│   ├── raw/                        # Raw API responses (JSON)
│   │   ├── osm_power.json          # OSM power lines/substations/towers
│   │   ├── osm_highways.json       # OSM primary/secondary highways
│   │   ├── srtm_elevation.json     # SRTM30m elevation grid
│   │   ├── pvgis_ghi.json          # PVGIS annual PV yield + GHI
│   │   ├── nasa_power_ghi.json     # NASA POWER daily GHI + temperature
│   │   └── esa_worldcover_lulc.json# ESA WorldCover LULC classification
│   └── processed/
│       ├── kallakurichi_parcels.json # Final analysis dataset (JSON)
│       └── kallakurichi_parcels.csv  # Final analysis dataset (CSV)
└── README.md
```

---

## 🌍 Data Sources

| Layer | Source | Resolution | Access |
|-------|--------|-----------|--------|
| **Land Use / Land Cover** | [ESA WorldCover 2020 v100](https://esa-worldcover.org) | 10 m | Terrascope WMS (free) |
| **Elevation + Slope** | [NASA SRTM30m](https://www.opentopodata.org/datasets/srtm30m/) | 30 m | OpenTopoData REST API (free) |
| **Annual PV Yield + GHI** | [PVGIS API v5.2 (ERA5)](https://re.jrc.ec.europa.eu/pvg_tools/) | ~28 km | JRC REST API (free, no key) |
| **Daily GHI + Temperature** | [NASA POWER v8 (MERRA-2)](https://power.larc.nasa.gov/) | 0.5° | NASA REST API (free, no key) |
| **Power Lines / Substations** | [OpenStreetMap Overpass](https://overpass-api.de) | Real geometry | Overpass API (free) |
| **Primary/Secondary Roads** | [OpenStreetMap Overpass](https://overpass-api.de) | Real geometry | Overpass API (free) |

> **No API keys required.** All data sources are publicly accessible.

---

## ⚙️ Suitability Factors & Scoring

All factors rated **1–4** (1 = least suitable, 4 = most suitable):

| Factor | Score 1 | Score 2 | Score 3 | Score 4 |
|--------|---------|---------|---------|---------|
| **Slope** (SRTM) | > 15° | 8–15° | 3–8° | < 3° |
| **LULC** (ESA) | Built-up / Water / Mangroves | Tree cover / Wetland | Cropland / Shrubland / Grassland | Bare/sparse vegetation |
| **GHI** (PVGIS) | < 1950 kWh/m²/yr | 1950–1965 | 1965–1980 | ≥ 1980 |
| **Grid Proximity** (OSM) | > 10 km | 5–10 km | 2–5 km | ≤ 2 km |
| **Road Access** (OSM) | > 8 km | 3–8 km | 1–3 km | ≤ 1 km |
| **Temperature** (NASA POWER) | > 27°C | 26–27°C | 25–26°C | ≤ 25°C |

**Suitability Score** = weighted sum of factor scores, normalised to sum to 1.

---

## 🗺️ Dashboard Features

- **Interactive Folium map** — choropleth circles + heat map mode, 4 basemap options
- **Real-time weight adjustment** — 6 factor sliders, auto-normalised
- **Filters** — by village, LULC class, max slope, max grid distance
- **Top 20 table** — colour-coded, all factor scores, real coordinates
- **Downloads** — CSV, GeoJSON exports
- **Data provenance panel** — links to original data sources

---

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/Athithiyanmr/kallakurichi-suitability-dashboard.git
cd kallakurichi-suitability-dashboard

# 2. Install
pip install -r requirements.txt

# 3. Run dashboard
streamlit run app.py
```

### Re-fetch data from scratch

```bash
# Run scripts in order — each saves to data/raw/
python scripts/01_fetch_osm_data.py
python scripts/02_fetch_elevation_srtm.py
python scripts/03_fetch_solar_pvgis_nasa.py
python scripts/04_fetch_esa_worldcover.py
python scripts/05_process_data.py
```

---

## 📊 Data Processing Pipeline

```
SRTM30m elevation grid (180 pts)
       ↓ finite differences
Slope (degrees) → Score 1–4
                                 ┐
ESA WorldCover WMS (396 pts)    │
       ↓ pixel decode            │
LULC class → Score 1–4          │
                                 │
PVGIS ERA5 (80 pts)             ├─→ KD-tree NN interp to 20×20 grid
       ↓                         │         (400 analysis points)
GHI, PV yield → Score 1–4       │         ↓
                                 │   Weighted sum →
NASA POWER MERRA-2 (80 pts)     │   Suitability score 1–4
       ↓                         │
Temp 2m → Score 1–4             │
                                 │
OSM Power lines (9,323 nodes)   │
       ↓ KD-tree distance        │
Power grid proximity → Score 1–4│
                                 │
OSM Highways (64,004 nodes)     │
       ↓ KD-tree distance        │
Road access → Score 1–4         ┘
```

---

## 📚 Citations

- **ESA WorldCover**: Zanaga et al. (2021). *ESA WorldCover 10m 2020 v100*. doi:10.5281/zenodo.5571936
- **SRTM**: Farr et al. (2007). *The Shuttle Radar Topography Mission*. doi:10.1029/2005RG000183
- **PVGIS**: Huld et al. (2012). *A new solar radiation database for estimating PV performance in Europe and Africa*. Solar Energy. doi:10.1016/j.solener.2012.03.006
- **NASA POWER**: Stackhouse et al. (2019). *NASA POWER: Prediction of Worldwide Energy Resources*. BAMS.
- **OpenStreetMap**: © OpenStreetMap contributors, ODbL license.

---

## 👤 Author

**Athithiyan MR** — Auroville Consulting  
Geospatial Data Scientist · Tamil Nadu, India  
GitHub: [@Athithiyanmr](https://github.com/Athithiyanmr)

---

## 📄 License

MIT — see [LICENSE](LICENSE)
