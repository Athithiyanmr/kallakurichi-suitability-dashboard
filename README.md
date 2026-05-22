# Kallakurichi Solar Suitability Dashboard

**Multi-source geospatial pipeline and interactive dashboard for utility-scale solar land suitability analysis in Kallakurichi District, Tamil Nadu, India.**

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Data: ESA WorldCover](https://img.shields.io/badge/LULC-ESA%20WorldCover%202021-blue)](https://esa-worldcover.org)
[![Data: NASA SRTM](https://img.shields.io/badge/elevation-NASA%20SRTM%2030m-orange)](https://www.opentopodata.org/datasets/srtm30m/)
[![Data: PVGIS](https://img.shields.io/badge/solar-PVGIS%20ERA5-yellow)](https://re.jrc.ec.europa.eu/pvg_tools/)
[![Data: OSM](https://img.shields.io/badge/infrastructure-OpenStreetMap-lightgrey)](https://overpass-api.de)

---

## Overview

This repository provides a **reproducible, open-data pipeline** that identifies and ranks bare/sparse land parcels in Kallakurichi District for utility-scale solar development. All data is fetched from authoritative public sources — no proprietary data or API keys required.

**Two independent interfaces are available:**

| Interface | Branch | Description |
|---|---|---|
| **Python pipeline + Streamlit** | `main` | Data fetch scripts 01–07, processing, legacy Streamlit app |
| **React 18 + Vite dashboard** | `react-dashboard` | SIG-grade interactive dashboard with live weighted overlay, Leaflet choropleth, Chart.js analytics |

---

## Methodology

### Study Area

**Kallakurichi District, Tamil Nadu, India**
Bounding box: 11.55–12.25°N, 78.55–79.25°E (~70 × 80 km)

### Analysis Approach

1. **LULC filtering** — ESA WorldCover 2021 v200 (10 m) raster is read via windowed access from AWS S3. Only class 60 (Bare/sparse vegetation) pixels are selected for solar analysis. Connected-component labelling identifies discrete patches; each patch ≥ 1 ha is catalogued with its centroid, area (ha / km²), and factor values.

2. **Factor scoring** — Six suitability factors are scored 1–4 using thresholds calibrated for Tamil Nadu:

| Factor | Source | Score 4 (Best) | Score 1 (Worst) |
|---|---|---|---|
| Slope | NASA SRTM 30 m | < 3° | > 15° |
| GHI | PVGIS ERA5 | ≥ 1 980 kWh/m²/yr | < 1 950 |
| Dist. to substation | OSM | ≤ 2 km | > 10 km |
| Dist. to highway | OSM | ≤ 1 km | > 8 km |
| Temperature | NASA POWER | ≤ 25 °C | > 27 °C |
| LULC class | ESA WorldCover | Bare/sparse (4) | Built-up (1) |

3. **Composite score** — Equal-weighted average of six factor scores (range 1–4). Suitability classes: Very High ≥ 3.5, High ≥ 2.75, Moderate ≥ 2.0, Low < 2.0.

---

## Project Structure

```
kallakurichi-suitability-dashboard/
│
├── scripts/
│   ├── config.py                      ← Shared configuration (bbox, thresholds, API params)
│   ├── utils.py                       ← Shared utilities (logging, I/O, scoring, KD-tree, OSM)
│   │
│   ├── 01_fetch_osm_data.py           ← OSM power lines + highways via Overpass API
│   ├── 02_fetch_elevation_srtm.py     ← NASA SRTM 30 m via OpenTopoData REST API
│   ├── 03_fetch_solar_pvgis_nasa.py   ← PVGIS ERA5 + NASA POWER solar radiation
│   ├── 04_fetch_esa_worldcover.py     ← ESA WorldCover 2020 LULC via Terrascope WMS
│   ├── 05_process_data.py             ← Grid-level processing + composite scoring
│   ├── 06_filter_solar_candidates.py  ← Post-filter barren patches (reads script 07 output)
│   └── 07_lulc_barren_analysis.py     ← Raster LULC map + barren land analysis
│
├── data/
│   ├── raw/
│   │   ├── osm_power.json             ← OSM power lines, substations, towers
│   │   ├── osm_highways.json          ← OSM primary/secondary/tertiary roads
│   │   ├── srtm_elevation.json        ← SRTM 30 m elevation grid (180 pts)
│   │   ├── pvgis_ghi.json             ← PVGIS annual GHI + PV yield (80 pts)
│   │   ├── nasa_power_ghi.json        ← NASA POWER daily GHI + temperature (80 pts)
│   │   ├── esa_worldcover_lulc.json   ← ESA WMS LULC sample grid (396 pts)
│   │   └── kallakurichi_lulc.tif      ← Clipped ESA raster (10 m, created by script 07)
│   │
│   ├── processed/
│   │   ├── kallakurichi_parcels.json  ← 400-parcel analysis dataset (JSON)
│   │   ├── kallakurichi_parcels.csv   ← 400-parcel analysis dataset (CSV)
│   │   ├── barren_analysis.json       ← Barren patch stats + factor averages
│   │   ├── barren_analysis.csv        ← All barren patches tabular
│   │   ├── solar_candidates.json      ← Filtered top-candidate patches
│   │   └── solar_candidates.geojson   ← GeoJSON for QGIS / Leaflet
│   │
│   └── outputs/
│       ├── lulc_map.png               ← Full LULC class map (10 m, 150 dpi)
│       └── barren_map.png             ← Barren land highlight map
│
├── app.py                             ← Legacy Streamlit dashboard
├── requirements.txt                   ← Python dependencies
└── README.md
```

---

## Data Sources

| Layer | Source | Resolution | Access |
|---|---|---|---|
| **Land Use / Land Cover** | [ESA WorldCover 2021 v200](https://esa-worldcover.org) | 10 m | AWS S3 public (script 07) + Terrascope WMS (script 04) |
| **Elevation / Slope** | [NASA SRTM 30 m](https://www.opentopodata.org/datasets/srtm30m/) | 30 m | OpenTopoData REST API (free, no key) |
| **Annual PV Yield + GHI** | [PVGIS API v5.2 (ERA5)](https://re.jrc.ec.europa.eu/pvg_tools/) | ~28 km | JRC REST API (free, no key) |
| **Daily GHI + Temperature** | [NASA POWER v8 (MERRA-2)](https://power.larc.nasa.gov/) | 0.5° | NASA REST API (free, no key) |
| **Power Lines / Substations** | [OpenStreetMap](https://overpass-api.de) | Real geometry | Overpass API (free, no key) |
| **Primary / Secondary Roads** | [OpenStreetMap](https://overpass-api.de) | Real geometry | Overpass API (free, no key) |

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/Athithiyanmr/kallakurichi-suitability-dashboard.git
cd kallakurichi-suitability-dashboard
pip install -r requirements.txt
```

> **Linux / headless servers:** `rasterio` requires GDAL. Use `pip install rasterio[gdal]` or install system GDAL first.

### 2. Run the pipeline (scripts must be run from the repo root)

```bash
# Step 1 — OSM infrastructure (power + highways)
python scripts/01_fetch_osm_data.py

# Step 2 — SRTM elevation
python scripts/02_fetch_elevation_srtm.py

# Step 3 — Solar radiation (PVGIS + NASA POWER)
python scripts/03_fetch_solar_pvgis_nasa.py

# Step 4 — ESA WorldCover LULC (WMS point sample)
python scripts/04_fetch_esa_worldcover.py

# Step 5 — Grid processing + composite scoring
python scripts/05_process_data.py

# Step 7 — Raster LULC analysis + barren land patches
# (run this before step 6)
python scripts/07_lulc_barren_analysis.py

# Step 6 — Filter and rank solar candidates
python scripts/06_filter_solar_candidates.py
```

> Scripts 01–04 fetch data from the internet and may take several minutes.
> Scripts 05–07 run locally on the downloaded data and complete in seconds.

### 3. Launch the Streamlit dashboard (legacy)

```bash
streamlit run app.py
```

---

## Script Reference

### `config.py`

Single source of truth for all pipeline constants. Edit this file to change the study area, grid density, API endpoints, or scoring thresholds without touching individual scripts.

Key sections:
- `LAT_MIN/MAX`, `LON_MIN/MAX` — district bounding box
- `LULC_CLASSES` — ESA class definitions with hex colours and solar scores
- `SLOPE_THRESHOLDS`, `GHI_THRESHOLDS`, etc. — factor scoring thresholds
- `ESA_S3_TILES` — AWS S3 URLs for ESA WorldCover v200 tiles
- `OVERPASS_MIRRORS` — fallback Overpass mirror list
- `CITATIONS` — full data source citations

### `utils.py`

Shared utility functions imported by all scripts. Key exports:

| Function | Description |
|---|---|
| `get_logger(name)` | Consistent stdout logger with `HH:MM:SS LEVEL message` format |
| `load_json(path)` | Load JSON with informative FileNotFoundError if missing |
| `save_json(data, path)` | Save JSON, auto-creating parent directories |
| `haversine_km(lat1, lon1, lat2, lon2)` | Great-circle distance in km |
| `pixel_area_ha(transform, lat)` | Area in ha of one 10 m raster pixel |
| `score_slope/ghi/power/road/temp/lulc(value)` | Factor scoring against config thresholds |
| `composite_score(scores, weights)` | Weighted average of factor scores |
| `suitability_class(score)` | Map score → Very High / High / Moderate / Low |
| `nn_interp(src_pts, src_vals, query_pts)` | KD-tree nearest-neighbour interpolation |
| `build_osm_kdtree(osm_json)` | Build a KD-tree from OSM element geometry |
| `extract_osm_nodes(osm_json)` | Extract deduplicated lat/lon node list |
| `overpass_fetch(query, label, path, logger)` | POST Overpass query with mirror fallback |
| `get_village(lat, lon)` | Assign village zone label from coordinates |

---

## Output Formats

### `data/processed/kallakurichi_parcels.json` / `.csv`

400-parcel analysis grid with one record per parcel. Key fields:

```
parcel_id          KLK-0001 … KLK-0400
village            Zone label (8 zones)
lat, lon           Parcel centroid (WGS84)
elevation_m        SRTM 30 m elevation
slope_deg          Terrain slope (finite-difference from SRTM)
slope_score        1–4
lulc_class         ESA WorldCover class code
lulc_name          Class display name
lulc_score         1–4
ghi_kwh_m2_yr      Annual in-plane irradiation (PVGIS ERA5)
pv_yield_kwh_kwp   Annual PV yield (PVGIS ERA5, kWh/kWp/yr)
ghi_score          1–4
ghi_daily          Daily GHI (NASA POWER MERRA-2, kWh/m²/day)
temp_c             Annual mean temperature 2 m (NASA POWER)
temp_score         1–4
power_dist_km      Distance to nearest OSM power line / substation
power_score        1–4
road_dist_km       Distance to nearest OSM primary/secondary road
road_score         1–4
suitability_score  Composite score (1.00–4.00)
suitability_class  Very High / High / Moderate / Low
```

### `data/processed/barren_analysis.json`

Patch-level statistics for all connected barren land areas (class 60) identified by script 07:

```json
{
  "district": "Kallakurichi, Tamil Nadu, India",
  "total_ha": 1234.5,
  "total_km2": 12.345,
  "patches_ge_1ha": 87,
  "avg_ghi_kwh_m2_yr": 1967.2,
  "avg_slope_deg": 2.3,
  "avg_power_dist_km": 4.1,
  "avg_road_dist_km": 2.8,
  "top_patches": [ ... ],
  "all_patches": [ ... ]
}
```

### `data/processed/solar_candidates.geojson`

GeoJSON FeatureCollection of filtered solar candidates (script 06 output). Load directly in QGIS, Leaflet, or MapLibre.

---

## React Dashboard

A full SIG-grade interactive dashboard is available on the `react-dashboard` branch:

```bash
git checkout react-dashboard
npm install
npm run dev
```

Features:
- Live interactive Leaflet choropleth map with score overlay
- Real-time weighted scoring sliders (adjust factor weights on the fly)
- Chart.js analytics: suitability doughnut, factor bars, village comparison, GHI scatter
- Sortable, filterable parcel data table
- Data provenance panel with citations and pipeline diagram

**Live demo:** [kallakurichi-solar-suitability](https://www.perplexity.ai/computer/a/kallakurichi-solar-suitability-CWUDpEj7TXmHT.PIPNFTQQ)

---

## Reproducibility Notes

- **Data is static.** Each script overwrites the same output file. Re-running scripts 01–04 will fetch fresh data from the APIs and may produce slightly different values (e.g. if OSM has been updated, or PVGIS API returns marginally different values).
- **Script 07 requires network access** to read ESA tiles via `/vsicurl/` (GDAL virtual filesystem). The tiles are read as windows — only the district region is downloaded, not the full 119 MB tile.
- **Script 04 (WMS sampling)** uses ESA WorldCover **2020 v100** via Terrascope WMS. **Script 07 (raster analysis)** uses **2021 v200** from AWS S3. Minor differences in class assignments are expected between the two approaches; script 07 is the authoritative source.
- All scripts are designed to run from the **repository root** (not from inside `scripts/`). The `sys.path` insertion at the top of each script handles import resolution automatically.

---

## Citations

If you use this data or methodology, please cite the underlying sources:

- **ESA WorldCover 2021 v200:** Zanaga D. et al. (2022). _ESA WorldCover 10 m 2021 v200_. Zenodo. doi:[10.5281/zenodo.7254221](https://doi.org/10.5281/zenodo.7254221)
- **NASA SRTM:** Farr T.G. et al. (2007). The Shuttle Radar Topography Mission. _Rev. Geophys._, 45, RG2004. doi:[10.1029/2005RG000183](https://doi.org/10.1029/2005RG000183)
- **PVGIS:** Huld T. et al. (2012). A new solar radiation database for estimating PV performance in Europe and Africa. _Solar Energy_. doi:[10.1016/j.solener.2012.03.006](https://doi.org/10.1016/j.solener.2012.03.006)
- **NASA POWER:** Stackhouse P.W. et al. (2019). NASA POWER: Prediction of Worldwide Energy Resources. _Bull. Amer. Meteor. Soc._
- **OpenStreetMap:** © OpenStreetMap contributors. [Open Database Licence (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/).

---

## License

MIT — see [LICENSE](LICENSE) for full text.

---

*Developed by [Auroville Consulting](https://aurovilleconsulting.com) · Kallakurichi District Solar Resource Assessment*
