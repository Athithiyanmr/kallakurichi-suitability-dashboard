"""
Kallakurichi Land Suitability Dashboard
Real-data weighted overlay analysis for solar energy siting
Data sources: ESA WorldCover, NASA SRTM, PVGIS, NASA POWER, OSM
Author: Athithiyan MR — Auroville Consulting
"""

import streamlit as st
import pandas as pd
import json, os
import folium
from folium.plugins import MarkerCluster, HeatMap
from streamlit_folium import st_folium
import numpy as np

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Kallakurichi Suitability Dashboard",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.main { background: #f8f9fa; }

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1b2a 0%, #1b263b 60%, #243447 100%);
    border-right: 2px solid #2d4a6b;
}
section[data-testid="stSidebar"] * { color: #d4e1f0 !important; }
section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 {
    color: #f0c040 !important; font-weight: 600 !important;
}
section[data-testid="stSidebar"] .stSlider > div > div > div { background: #f0c040 !important; }

.kpi-card {
    background: white; border-radius: 14px; padding: 16px 20px;
    box-shadow: 0 2px 16px rgba(0,0,0,0.07);
    border-top: 3px solid #f0c040; margin-bottom: 8px;
}
.kpi-label { font-size: 11px; color: #888; font-weight: 600;
             text-transform: uppercase; letter-spacing: 0.6px; }
.kpi-value { font-size: 26px; font-weight: 700; color: #0d1b2a; margin-top: 3px; }
.kpi-sub   { font-size: 11px; color: #aaa; margin-top: 2px; }

.source-badge {
    display: inline-block; background: #e8f0fe; color: #1a56db;
    border-radius: 4px; padding: 2px 7px; font-size: 11px;
    font-weight: 600; margin: 2px;
}
.stDownloadButton > button {
    background: linear-gradient(135deg, #1b263b, #2d4a6b);
    color: #f0c040 !important; border: none; border-radius: 8px;
    padding: 10px 22px; font-weight: 700; font-size: 13px;
    letter-spacing: 0.3px; transition: all 0.2s;
}
.stDownloadButton > button:hover { transform: translateY(-1px); opacity: 0.9; }
h1, h2, h3 { color: #0d1b2a !important; }
</style>
""", unsafe_allow_html=True)

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    base = os.path.dirname(__file__)
    p = os.path.join(base, "data", "processed", "kallakurichi_parcels.json")
    with open(p) as f:
        recs = json.load(f)
    return pd.DataFrame(recs)

df_raw = load_data()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ☀️ Suitability Dashboard")
    st.markdown("**Kallakurichi District · Tamil Nadu**")
    st.markdown("---")

    st.markdown("### ⚖️ Factor Weights")
    st.caption("Drag sliders to re-weight factors. Auto-normalised to sum = 1.0.")

    w_slope = st.slider("🏔️ Slope (SRTM)",           0, 10, 3, key="slope")
    w_lulc  = st.slider("🗺️ LULC (ESA WorldCover)",  0, 10, 3, key="lulc")
    w_ghi   = st.slider("☀️ Solar GHI (PVGIS)",       0, 10, 3, key="ghi")
    w_power = st.slider("⚡ Grid Proximity (OSM)",    0, 10, 2, key="power")
    w_road  = st.slider("🛣️ Road Access (OSM)",       0, 10, 1, key="road")
    w_temp  = st.slider("🌡️ Temperature (NASA PWR)", 0, 10, 1, key="temp")

    total = w_slope + w_lulc + w_ghi + w_power + w_road + w_temp
    if total == 0:
        st.error("Set at least one weight > 0")
        st.stop()

    nw = {k: v/total for k, v in {
        "slope": w_slope, "lulc": w_lulc, "ghi": w_ghi,
        "power": w_power, "road": w_road, "temp": w_temp
    }.items()}

    st.markdown(
        f'<div style="background:#1b3a5c;border-radius:8px;padding:10px 12px;'
        f'margin-top:6px;font-size:12px;color:#f0c040;font-weight:600;">'
        f'✅ Slope {nw["slope"]:.0%} · LULC {nw["lulc"]:.0%} · GHI {nw["ghi"]:.0%}<br>'
        f'Grid {nw["power"]:.0%} · Road {nw["road"]:.0%} · Temp {nw["temp"]:.0%}</div>',
        unsafe_allow_html=True
    )

    st.markdown("---")
    st.markdown("### 🔍 Filters")
    villages = ["All"] + sorted(df_raw["village"].unique().tolist())
    sel_village = st.selectbox("Village / Taluk", villages)

    lulc_types = ["All"] + sorted(df_raw["lulc_name"].unique().tolist())
    sel_lulc = st.selectbox("LULC Class", lulc_types)

    max_slope = st.slider("Max Slope (°)", 0.0, 20.0, 10.0, 0.5)
    max_power_dist = st.slider("Max Grid Distance (km)", 0.0, 30.0, 30.0, 1.0)

    st.markdown("---")
    st.markdown("### 🗺️ Map Style")
    basemap = st.selectbox("Basemap", [
        "CartoDB Positron", "OpenStreetMap",
        "CartoDB DarkMatter", "Esri Satellite"
    ])
    map_mode = st.radio("Map Mode", ["Choropleth circles", "Heat map"], horizontal=True)

    st.markdown("---")
    st.markdown(
        '<small style="color:#7a9cc0;">Data sources: ESA WorldCover 2020 · '
        'NASA SRTM30m · PVGIS ERA5 · NASA POWER MERRA-2 · OSM Overpass</small>',
        unsafe_allow_html=True
    )

# ── Compute suitability ───────────────────────────────────────────────────────
df = df_raw.copy()
df["suitability_score"] = (
    nw["slope"] * df["slope_score"] +
    nw["lulc"]  * df["lulc_score"]  +
    nw["ghi"]   * df["ghi_score"]   +
    nw["power"] * df["power_score"] +
    nw["road"]  * df["road_score"]  +
    nw["temp"]  * df["temp_score"]
).round(4)

bins   = [0, 1.75, 2.5, 3.25, 4.01]
labels = ["Low (1)", "Moderate (2)", "High (3)", "Very High (4)"]
df["suitability_class"] = pd.cut(df["suitability_score"], bins=bins, labels=labels)

# Apply filters
if sel_village != "All":
    df = df[df["village"] == sel_village]
if sel_lulc != "All":
    df = df[df["lulc_name"] == sel_lulc]
df = df[df["slope_deg"] <= max_slope]
df = df[df["power_dist_km"] <= max_power_dist]

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# ☀️ Kallakurichi Solar Suitability Dashboard")
st.markdown(
    "Weighted overlay analysis · Real data: "
    '<span class="source-badge">ESA WorldCover</span>'
    '<span class="source-badge">NASA SRTM</span>'
    '<span class="source-badge">PVGIS ERA5</span>'
    '<span class="source-badge">NASA POWER</span>'
    '<span class="source-badge">OSM</span>',
    unsafe_allow_html=True
)
st.markdown("---")

# ── KPI row ───────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5, c6 = st.columns(6)
n_high  = len(df[df["suitability_class"].isin(["High (3)", "Very High (4)"])])
avg_ghi = df["ghi_kwh_m2_yr"].mean() if len(df) else 0
avg_ey  = df["pv_yield_kwh_kwp"].mean() if len(df) else 0

def kpi(label, value, sub):
    return f'<div class="kpi-card"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div><div class="kpi-sub">{sub}</div></div>'

with c1: st.markdown(kpi("Parcels", len(df), "after filters"), unsafe_allow_html=True)
with c2: st.markdown(kpi("Avg Score", f"{df['suitability_score'].mean():.2f}" if len(df) else "—", "out of 4.0"), unsafe_allow_html=True)
with c3: st.markdown(kpi("High Suit.", str(n_high), "score ≥ 2.5"), unsafe_allow_html=True)
with c4: st.markdown(kpi("Best Score", f"{df['suitability_score'].max():.2f}" if len(df) else "—", "top parcel"), unsafe_allow_html=True)
with c5: st.markdown(kpi("Avg GHI", f"{avg_ghi:.0f}", "kWh/m²/yr PVGIS"), unsafe_allow_html=True)
with c6: st.markdown(kpi("Avg PV Yield", f"{avg_ey:.0f}", "kWh/kWp/yr"), unsafe_allow_html=True)

st.markdown("")

# ── Map + panels ──────────────────────────────────────────────────────────────
map_col, panel_col = st.columns([2, 1])

TILES = {
    "CartoDB Positron":   ("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
                           "© OpenStreetMap © CARTO"),
    "OpenStreetMap":      ("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                           "© OpenStreetMap contributors"),
    "CartoDB DarkMatter": ("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
                           "© OpenStreetMap © CARTO"),
    "Esri Satellite":     ("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                           "Tiles © Esri"),
}

def score_color(s):
    if s >= 3.25:   return "#1a6b1a"
    elif s >= 2.5:  return "#4caf50"
    elif s >= 1.75: return "#ff9800"
    else:           return "#f44336"

def score_fill(s):
    if s >= 3.25:   return "#43a047"
    elif s >= 2.5:  return "#a5d6a7"
    elif s >= 1.75: return "#ffcc80"
    else:           return "#ef9a9a"

with map_col:
    st.markdown("### 🗺️ Suitability Map")
    if len(df) == 0:
        st.warning("No parcels match current filters.")
    else:
        clat = df["lat"].mean(); clon = df["lon"].mean()
        tile_url, tile_attr = TILES[basemap]
        m = folium.Map(location=[clat, clon], zoom_start=10,
                       tiles=tile_url, attr=tile_attr, prefer_canvas=True)

        # Legend
        legend = """
        <div style="position:fixed;bottom:28px;right:28px;z-index:1000;
                    background:white;padding:12px 16px;border-radius:12px;
                    box-shadow:0 4px 18px rgba(0,0,0,0.18);font-family:Inter,sans-serif;">
          <b style="font-size:12px;color:#0d1b2a;">Suitability Score</b>
          <div style="margin-top:7px;">
          """ + "".join([
            f'<div style="display:flex;align-items:center;margin-bottom:5px;">'
            f'<div style="width:13px;height:13px;border-radius:50%;background:{c};margin-right:8px;"></div>'
            f'<span style="font-size:11px;">{lbl}</span></div>'
            for c, lbl in [
                ("#1a6b1a", "Very High (3.25–4.0)"),
                ("#4caf50", "High (2.5–3.25)"),
                ("#ff9800", "Moderate (1.75–2.5)"),
                ("#f44336", "Low (1.0–1.75)"),
            ]
        ]) + "</div></div>"
        m.get_root().html.add_child(folium.Element(legend))

        if map_mode == "Heat map":
            heat_data = [[row["lat"], row["lon"], row["suitability_score"]]
                         for _, row in df.iterrows()]
            HeatMap(heat_data, radius=20, blur=15,
                    gradient={0.2: "#f44336", 0.5: "#ff9800",
                               0.7: "#4caf50", 1.0: "#1a6b1a"}).add_to(m)
        else:
            for _, row in df.iterrows():
                sc   = row["suitability_score"]
                col  = score_color(sc)
                fill = score_fill(sc)
                tt   = f"""
                <div style="font-family:Inter,sans-serif;min-width:220px;">
                  <b style="font-size:13px;color:#0d1b2a;">{row['parcel_id']}</b>
                  <div style="color:#666;font-size:11px;margin-bottom:6px;">{row['village']}</div>
                  <table style="font-size:11px;width:100%;border-collapse:collapse;">
                    <tr style="background:#f5f5f5;"><td colspan="2" style="padding:4px 6px;font-weight:700;color:{col};">
                      Suitability: {sc:.3f}/4.0</td></tr>
                    <tr><td style="color:#888;padding:3px 6px;">Slope</td>
                        <td style="text-align:right;padding:3px 6px;">{row['slope_score']}/4 · {row['slope_deg']:.1f}°</td></tr>
                    <tr style="background:#fafafa;"><td style="color:#888;padding:3px 6px;">LULC</td>
                        <td style="text-align:right;padding:3px 6px;">{row['lulc_score']}/4 · {row['lulc_name']}</td></tr>
                    <tr><td style="color:#888;padding:3px 6px;">GHI</td>
                        <td style="text-align:right;padding:3px 6px;">{row['ghi_score']}/4 · {row['ghi_kwh_m2_yr']:.0f} kWh/m²/yr</td></tr>
                    <tr style="background:#fafafa;"><td style="color:#888;padding:3px 6px;">PV Yield</td>
                        <td style="text-align:right;padding:3px 6px;">{row['pv_yield_kwh_kwp']:.0f} kWh/kWp/yr</td></tr>
                    <tr><td style="color:#888;padding:3px 6px;">Grid dist.</td>
                        <td style="text-align:right;padding:3px 6px;">{row['power_score']}/4 · {row['power_dist_km']:.1f} km</td></tr>
                    <tr style="background:#fafafa;"><td style="color:#888;padding:3px 6px;">Road dist.</td>
                        <td style="text-align:right;padding:3px 6px;">{row['road_score']}/4 · {row['road_dist_km']:.1f} km</td></tr>
                    <tr><td style="color:#888;padding:3px 6px;">Elevation</td>
                        <td style="text-align:right;padding:3px 6px;">{row['elevation_m']:.0f} m</td></tr>
                    <tr style="background:#fafafa;"><td style="color:#888;padding:3px 6px;">Temp</td>
                        <td style="text-align:right;padding:3px 6px;">{row['temp_score']}/4 · {row['temp_c']:.1f}°C</td></tr>
                    <tr><td style="color:#888;padding:3px 6px;">Coords</td>
                        <td style="text-align:right;font-size:10px;padding:3px 6px;">{row['lat']:.4f}°N, {row['lon']:.4f}°E</td></tr>
                  </table>
                </div>"""
                folium.CircleMarker(
                    location=[row["lat"], row["lon"]],
                    radius=7,
                    color=col, fill=True, fill_color=fill,
                    fill_opacity=0.80, weight=1.5,
                    tooltip=folium.Tooltip(tt, sticky=True),
                ).add_to(m)

        st_folium(m, width=None, height=530, returned_objects=[])

with panel_col:
    st.markdown("### 📊 Analysis Panels")

    tab1, tab2, tab3 = st.tabs(["Score Dist.", "Village", "Data Sources"])

    with tab1:
        st.markdown("**Suitability class breakdown**")
        cls_order = ["Very High (4)", "High (3)", "Moderate (2)", "Low (1)"]
        cls_colors_map = {"Very High (4)":"#1a6b1a","High (3)":"#4caf50",
                          "Moderate (2)":"#ff9800","Low (1)":"#f44336"}
        cls_counts = df["suitability_class"].value_counts().reindex(cls_order, fill_value=0)
        for cls, cnt in cls_counts.items():
            pct = cnt / max(len(df),1) * 100
            bar = int(pct * 1.4)
            col = cls_colors_map.get(cls, "#999")
            st.markdown(
                f'<div style="margin-bottom:10px;">'
                f'<div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:3px;">'
                f'<b style="color:#333;">{cls}</b>'
                f'<span style="color:#666;">{cnt} ({pct:.0f}%)</span></div>'
                f'<div style="background:#f0f0f0;border-radius:5px;height:9px;">'
                f'<div style="background:{col};height:9px;border-radius:5px;width:{bar}%;"></div></div></div>',
                unsafe_allow_html=True
            )
        st.markdown("---")
        st.markdown("**Factor score averages**")
        factors = [
            ("Slope",  df["slope_score"].mean(),  "#78909c"),
            ("LULC",   df["lulc_score"].mean(),   "#66bb6a"),
            ("GHI",    df["ghi_score"].mean(),     "#f0c040"),
            ("Grid",   df["power_score"].mean(),   "#42a5f5"),
            ("Road",   df["road_score"].mean(),    "#ab47bc"),
            ("Temp",   df["temp_score"].mean(),    "#ff7043"),
        ]
        for name, avg, col in factors:
            pct = avg / 4 * 100
            bar = int(pct * 1.4)
            st.markdown(
                f'<div style="margin-bottom:8px;">'
                f'<div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:2px;">'
                f'<span style="font-weight:600;color:#333;">{name}</span>'
                f'<span style="color:#666;">{avg:.2f}/4</span></div>'
                f'<div style="background:#f0f0f0;border-radius:5px;height:7px;">'
                f'<div style="background:{col};height:7px;border-radius:5px;width:{bar}%;"></div></div></div>',
                unsafe_allow_html=True
            )

    with tab2:
        st.markdown("**Village-level average suitability**")
        v_avg = df.groupby("village")["suitability_score"].agg(["mean","count"]).sort_values("mean", ascending=False)
        for v, row in v_avg.iterrows():
            m_val = row["mean"]; cnt_v = int(row["count"])
            col = "#1a6b1a" if m_val>=3 else "#ff9800" if m_val>=2.5 else "#f44336"
            bg  = "#c8e6c9" if m_val>=3 else "#fff9c4" if m_val>=2.5 else "#ffcdd2"
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'margin-bottom:6px;padding:6px 10px;background:white;border-radius:8px;'
                f'box-shadow:0 1px 4px rgba(0,0,0,0.06);">'
                f'<span style="font-size:12px;font-weight:600;color:#333;">{v}</span>'
                f'<div style="display:flex;align-items:center;gap:8px;">'
                f'<span style="font-size:10px;color:#888;">{cnt_v} pts</span>'
                f'<span style="background:{bg};color:{col};padding:2px 8px;'
                f'border-radius:12px;font-size:11px;font-weight:700;">{m_val:.2f}</span>'
                f'</div></div>',
                unsafe_allow_html=True
            )

    with tab3:
        st.markdown("**Real data sources used**")
        sources = [
            ("ESA WorldCover 2020 v100", "LULC classification (10m)",
             "Terrascope WMS", "https://esa-worldcover.org"),
            ("NASA SRTM30m", "Elevation + Slope",
             "OpenTopoData.org API", "https://www.opentopodata.org"),
            ("PVGIS API v5.2 ERA5", "Annual PV yield, GHI",
             "JRC PVGIS", "https://re.jrc.ec.europa.eu/pvg_tools"),
            ("NASA POWER v8 MERRA-2", "Daily GHI, Temperature",
             "NASA POWER", "https://power.larc.nasa.gov"),
            ("OpenStreetMap Overpass", "Power lines, Substations",
             "OSM Overpass API", "https://overpass-api.de"),
            ("OpenStreetMap Overpass", "Primary/Secondary Roads",
             "OSM Overpass API", "https://overpass-api.de"),
        ]
        for name, layer, provider, url in sources:
            st.markdown(
                f'<div style="background:white;border-radius:8px;padding:8px 12px;'
                f'margin-bottom:8px;box-shadow:0 1px 4px rgba(0,0,0,0.06);">'
                f'<div style="font-size:12px;font-weight:700;color:#0d1b2a;">{name}</div>'
                f'<div style="font-size:11px;color:#555;margin-top:2px;">Layer: {layer}</div>'
                f'<div style="font-size:11px;color:#888;">Provider: {provider}</div>'
                f'<a href="{url}" target="_blank" style="font-size:10px;color:#1a56db;">{url}</a></div>',
                unsafe_allow_html=True
            )

# ── Top 20 table ──────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 🏆 Top 20 Most Suitable Parcels")
st.caption("Sorted by weighted suitability score · All real data · Click column headers to sort")

top20 = (
    df.sort_values("suitability_score", ascending=False)
    .head(20)
    [[
        "parcel_id", "village", "lat", "lon",
        "suitability_score",
        "slope_score", "slope_deg",
        "lulc_score", "lulc_name",
        "ghi_score", "ghi_kwh_m2_yr", "pv_yield_kwh_kwp",
        "power_score", "power_dist_km",
        "road_score", "road_dist_km",
        "temp_score", "temp_c",
        "elevation_m",
    ]]
    .reset_index(drop=True)
)
top20.index += 1

top20_disp = top20.rename(columns={
    "parcel_id": "Parcel ID", "village": "Village",
    "lat": "Lat", "lon": "Lon",
    "suitability_score": "Score ▼",
    "slope_score": "Slope▸", "slope_deg": "Slope(°)",
    "lulc_score": "LULC▸", "lulc_name": "LULC Class",
    "ghi_score": "GHI▸", "ghi_kwh_m2_yr": "GHI(kWh/m²/yr)", "pv_yield_kwh_kwp": "PV Yield",
    "power_score": "Grid▸", "power_dist_km": "Grid(km)",
    "road_score": "Road▸", "road_dist_km": "Road(km)",
    "temp_score": "Temp▸", "temp_c": "Temp(°C)",
    "elevation_m": "Elev(m)",
})

def colour_score(val):
    try:
        v = float(val)
        if v >= 3.25:   return "background:#c8e6c9;color:#1b5e20;font-weight:700"
        elif v >= 2.5:  return "background:#dcedc8;color:#558b2f;font-weight:700"
        elif v >= 1.75: return "background:#fff9c4;color:#f57f17"
        else:           return "background:#ffcdd2;color:#b71c1c"
    except: return ""

score_cols = ["Score ▼", "Slope▸", "LULC▸", "GHI▸", "Grid▸", "Road▸", "Temp▸"]
styled = (
    top20_disp.style
    .applymap(colour_score, subset=score_cols)
    .format({
        "Lat": "{:.4f}", "Lon": "{:.4f}",
        "Score ▼": "{:.3f}", "Slope(°)": "{:.1f}",
        "GHI(kWh/m²/yr)": "{:.0f}", "PV Yield": "{:.0f}",
        "Grid(km)": "{:.2f}", "Road(km)": "{:.2f}",
        "Temp(°C)": "{:.1f}", "Elev(m)": "{:.0f}",
    })
    .set_table_styles([
        {"selector": "thead th",
         "props": [("background","#0d1b2a"),("color","#f0c040"),
                   ("font-size","11px"),("padding","9px 10px"),("text-align","center")]},
        {"selector": "tbody td",
         "props": [("font-size","11px"),("padding","7px 10px"),("text-align","center")]},
        {"selector": "tbody tr:nth-child(even)",
         "props": [("background-color","#f9f9f9")]},
    ])
)
st.dataframe(styled, use_container_width=True, height=560)

# ── Downloads ─────────────────────────────────────────────────────────────────
dl1, dl2, dl3, _ = st.columns([1, 1, 1, 2])
with dl1:
    st.download_button("⬇️ Top 20 CSV", top20.to_csv(index_label="Rank"),
                       "kallakurichi_top20.csv", "text/csv")
with dl2:
    all_csv = df.sort_values("suitability_score", ascending=False).to_csv(index=False)
    st.download_button("⬇️ All Parcels CSV", all_csv,
                       "kallakurichi_all.csv", "text/csv")
with dl3:
    geojson_features = [
        {"type":"Feature",
         "geometry":{"type":"Point","coordinates":[row["lon"],row["lat"]]},
         "properties":{k: row[k] for k in ["parcel_id","village","suitability_score",
                                             "slope_score","lulc_score","ghi_score",
                                             "power_score","road_score","temp_score",
                                             "ghi_kwh_m2_yr","pv_yield_kwh_kwp",
                                             "power_dist_km","road_dist_km"]}}
        for _, row in df.iterrows()
    ]
    geojson_str = json.dumps({"type":"FeatureCollection","features":geojson_features}, indent=2)
    st.download_button("⬇️ GeoJSON", geojson_str,
                       "kallakurichi_parcels.geojson", "application/json")

# ── Methodology ───────────────────────────────────────────────────────────────
st.markdown("---")
with st.expander("📋 Methodology · Data Processing · Scoring Rubric"):
    st.markdown(f"""
    ### Weighted Overlay Formula

    > **Score = {nw['slope']:.2f}×Slope + {nw['lulc']:.2f}×LULC + {nw['ghi']:.2f}×GHI + {nw['power']:.2f}×Grid + {nw['road']:.2f}×Road + {nw['temp']:.2f}×Temp**

    All factors scored **1–4** (1 = least suitable, 4 = most suitable).

    ### Factor Scoring Rubric

    | Factor | Score 1 | Score 2 | Score 3 | Score 4 | Source |
    |--------|---------|---------|---------|---------|--------|
    | **Slope** | > 15° | 8–15° | 3–8° | < 3° | NASA SRTM30m |
    | **LULC** | Built-up / Water / Mangroves | Tree cover / Wetland | Cropland / Shrubland / Grassland | Bare/sparse veg | ESA WorldCover 2020 |
    | **GHI** | < 1950 kWh/m²/yr | 1950–1965 | 1965–1980 | ≥ 1980 | PVGIS API ERA5 |
    | **Grid Prox.** | > 10 km | 5–10 km | 2–5 km | ≤ 2 km | OSM power lines |
    | **Road Access** | > 8 km | 3–8 km | 1–3 km | ≤ 1 km | OSM highways |
    | **Temperature** | > 27°C | 26–27°C | 25–26°C | ≤ 25°C | NASA POWER MERRA-2 |

    ### Suitability Classes
    | Class | Score Range |
    |-------|-------------|
    | Very High (4) | 3.25–4.0 |
    | High (3) | 2.5–3.25 |
    | Moderate (2) | 1.75–2.5 |
    | Low (1) | 1.0–1.75 |

    ### Data Processing Pipeline
    1. **SRTM Elevation** — 180 points sampled via OpenTopoData REST API · Slope computed from finite differences
    2. **ESA WorldCover** — 396 pixels sampled via Terrascope WMS (EPSG:3857) · RGB decoded to ESA class codes
    3. **PVGIS GHI** — 80 grid points via PVGIS API v5.2 (ERA5 database) · Annual in-plane irradiation H(i)_y
    4. **NASA POWER** — 80 grid points climatology · Daily GHI + mean temperature
    5. **OSM Power** — 2,577 elements (power lines + substations + towers) via Overpass API
    6. **OSM Roads** — 1,543 highway segments (primary/secondary/tertiary) via Overpass API
    7. **Spatial join** — KD-tree nearest-neighbour interpolation to 400-point analysis grid

    > Analysis grid: 20×20 regular grid · Bbox: 11.62–12.08°N, 78.63–79.33°E
    """)
