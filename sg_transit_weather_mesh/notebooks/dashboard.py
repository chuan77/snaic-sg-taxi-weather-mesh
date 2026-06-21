# sg_transit_weather_mesh/notebooks/dashboard.py
import marimo as __marimo

app = __marimo.App(width="full")


@app.cell
def init_libraries():
    import math
    import os
    import sys

    import marimo as mo
    import pandas as pd
    import plotly.express as px

    _pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    if _pkg_root not in sys.path:
        sys.path.insert(0, _pkg_root)

    from sg_transit_weather_mesh.notebooks.dashboard_data import (
        REGION_COORDS,
        generate_biz_data,
    )
    return REGION_COORDS, generate_biz_data, math, mo, pd, px


@app.cell
def inject_dark_theme(mo):
    # Best-effort page-wide dark background injection
    return mo.Html("""<style>
body, .marimo { background-color: #0b1220 !important; }
</style>""")


@app.cell
def load_data(generate_biz_data):
    df_biz = generate_biz_data(seed=42)
    return df_biz,


@app.cell
def build_left_panel(df_biz, mo):
    _dates = sorted(df_biz["date"].unique())
    _latest = _dates[-1]
    _prev = _dates[-2]

    _fleet_now = int(df_biz[df_biz["date"] == _latest]["active_users"].sum())
    _fleet_prev = int(df_biz[df_biz["date"] == _prev]["active_users"].sum())
    _pct = round((_fleet_now - _fleet_prev) / max(_fleet_prev, 1) * 100, 1)
    _arrow = "▲" if _pct >= 0 else "▼"
    _trend_col = "#22c55e" if _pct >= 0 else "#ef4444"

    # Prevalent weather derived from latest-day conversion rate
    _cvr_mean = float(df_biz[df_biz["date"] == _latest]["conversion_rate"].mean())
    _weather = "Partly Cloudy (Day)" if _cvr_mean > 7.0 else "Passing Showers"
    _rain_alert = _weather == "Passing Showers"
    _TEMP = 28.4

    left_panel = mo.Html(f"""
<div style="font-family:system-ui,-apple-system,sans-serif; color:#f1f5f9;">

  <div style="font-size:10px; font-weight:700; letter-spacing:2px; text-transform:uppercase;
              color:#475569; padding-bottom:10px; border-bottom:1px solid #1e293b; margin-bottom:20px;">
    📊 Operational KPI Metrics
  </div>

  <!-- Active Fleet Density -->
  <div style="background:#0f172a; border:1px solid #1e293b; border-radius:10px;
              padding:16px 18px; margin-bottom:12px;">
    <div style="font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:1.5px;
                color:#475569; margin-bottom:6px;">Active Fleet Density</div>
    <div style="font-size:36px; font-weight:800; color:#f1f5f9;
                font-variant-numeric:tabular-nums; line-height:1;">{_fleet_now:,}</div>
    <div style="font-size:11px; color:#64748b; margin-top:3px;">Active Users (fleet proxy)</div>
    <div style="font-size:12px; font-weight:700; color:{_trend_col}; margin-top:9px;">
      {_arrow} {abs(_pct)}% vs previous day
    </div>
  </div>

  <!-- Mean Grid Temperature -->
  <div style="background:#0f172a; border:1px solid #1e293b; border-radius:10px;
              padding:16px 18px; margin-bottom:12px;">
    <div style="font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:1.5px;
                color:#475569; margin-bottom:6px;">Mean Grid Temperature</div>
    <div style="font-size:36px; font-weight:800; color:#f1f5f9; line-height:1;">
      {_TEMP}&thinsp;<span style="font-size:20px;">°C</span>
    </div>
    <div style="font-size:12px; font-weight:700; color:#22c55e; margin-top:9px;">► Nominal</div>
  </div>

  <!-- Prevalent Weather -->
  <div style="background:#0f172a;
              border:1px solid {"#7c2d12" if _rain_alert else "#1e293b"};
              border-radius:10px; padding:16px 18px;">
    <div style="font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:1.5px;
                color:#475569; margin-bottom:6px;">Prevalent Weather</div>
    <div style="font-size:19px; font-weight:700; color:#f1f5f9; line-height:1.35;">{_weather}</div>
    <div style="font-size:12px; font-weight:700; margin-top:9px;
                color:{"#f97316" if _rain_alert else "#22c55e"};">
      {"⚠️ Rain Alert Active" if _rain_alert else "✓ No Active Alerts"}
    </div>
  </div>

</div>
""")
    return left_panel,


@app.cell
def build_center_map(df_biz, mo, px, REGION_COORDS):
    _agg = df_biz.groupby("region").agg(
        active_users=("active_users", "sum"),
        revenue=("revenue", lambda x: round(float(x.sum()), 2)),
        cvr=("conversion_rate", lambda x: round(float(x.mean()), 2)),
    ).reset_index()
    _agg["lat"] = _agg["region"].map(lambda r: REGION_COORDS[r][0])
    _agg["lon"] = _agg["region"].map(lambda r: REGION_COORDS[r][1])

    _fig = px.scatter_map(
        _agg,
        lat="lat",
        lon="lon",
        size="active_users",
        color="cvr",
        color_continuous_scale="Plasma",
        hover_name="region",
        hover_data={
            "active_users": True,
            "revenue": True,
            "cvr": True,
            "lat": False,
            "lon": False,
        },
        labels={
            "active_users": "Active Users",
            "revenue": "Revenue (SGD)",
            "cvr": "CVR %",
        },
        size_max=65,
        zoom=10.2,
        center={"lat": 1.352, "lon": 103.819},
        map_style="carto-darkmatter",
        height=560,
    )
    _fig.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        paper_bgcolor="#0b1220",
        plot_bgcolor="#0b1220",
        coloraxis_colorbar=dict(
            title="CVR %",
            thickness=10,
            len=0.55,
            tickfont=dict(color="#94a3b8"),
            title_font=dict(color="#94a3b8"),
        ),
        font=dict(color="#94a3b8"),
    )

    center_panel = mo.vstack([
        mo.Html("""
<div style="font-family:system-ui,-apple-system,sans-serif;">
  <div style="font-size:10px; font-weight:700; letter-spacing:2px; text-transform:uppercase;
              color:#475569; padding-bottom:10px; border-bottom:1px solid #1e293b; margin-bottom:12px;">
    🗺️ Geospatial Density Mesh View
  </div>
  <div style="font-size:10px; color:#334155; margin-bottom:10px; font-weight:500;">
    ● Drag to pan &nbsp;&nbsp;/&nbsp;&nbsp; Scroll to zoom &nbsp;&nbsp;/&nbsp;&nbsp; Hover for region metrics
  </div>
</div>
"""),
        mo.ui.plotly(_fig),
    ], gap=0)
    return center_panel,


@app.cell
def create_controls(mo):
    """Slider and radio widgets — defined once, never recreated on prediction change."""
    lat_slider = mo.ui.slider(
        start=1.20,
        stop=1.50,
        step=0.01,
        value=1.35,
        label="Latitude",
        show_value=True,
        full_width=True,
    )
    lon_slider = mo.ui.slider(
        start=103.60,
        stop=104.00,
        step=0.01,
        value=103.82,
        label="Longitude",
        show_value=True,
        full_width=True,
    )
    weather_radio = mo.ui.radio(
        options=["Clear", "Partly Cloudy", "Cloudy", "Passing Showers", "Heavy Rain"],
        value="Partly Cloudy",
        label="Weather Mode",
        inline=False,
    )
    return lat_slider, lon_slider, weather_radio


@app.cell
def run_prediction(lat_slider, lon_slider, weather_radio, mo, math):
    """Reactive prediction — only this cell (and its dependents) rerenders on slider change."""
    _W = {
        "Clear": 1.00,
        "Partly Cloudy": 0.93,
        "Cloudy": 0.85,
        "Passing Showers": 0.65,
        "Heavy Rain": 0.40,
    }
    # Taxi supply falls off with distance from Marina Bay / CBD centroid
    _CBD = (1.2867, 103.8545)
    _dist_km = math.sqrt(
        (lat_slider.value - _CBD[0]) ** 2 + (lon_slider.value - _CBD[1]) ** 2
    ) * 111.0
    _supply = max(5, int(320 * math.exp(-_dist_km / 9.0) * _W.get(weather_radio.value, 1.0)))

    _col = "#22c55e" if _supply > 150 else ("#f59e0b" if _supply > 60 else "#ef4444")
    _label = (
        "High Availability"
        if _supply > 150
        else ("Moderate" if _supply > 60 else "Low — Surge Likely")
    )

    prediction_display = mo.Html(f"""
<div style="font-family:system-ui,-apple-system,sans-serif;
            background:#0f172a; border:2px solid {_col}33; border-radius:10px;
            padding:18px 16px; text-align:center; margin-top:4px;">
  <div style="font-size:10px; font-weight:700; letter-spacing:1.5px; text-transform:uppercase;
              color:#475569; margin-bottom:10px;">⚡ Predicted Taxi Supply</div>
  <div style="font-size:56px; font-weight:900; color:{_col}; line-height:1;
              font-variant-numeric:tabular-nums;">{_supply}</div>
  <div style="color:#64748b; font-size:12px; margin-top:4px;">Vehicles</div>
  <div style="font-size:12px; font-weight:700; color:{_col}; margin-top:8px;">{_label}</div>
  <div style="height:1px; background:#1e293b; margin:12px 4px;"></div>
  <div style="font-size:10px; color:#334155; line-height:1.6;">
    Lat {lat_slider.value:.2f} &nbsp;·&nbsp; Lon {lon_slider.value:.2f}
    <br/>{_dist_km:.1f} km from CBD centroid
  </div>
</div>
""")
    return prediction_display,


@app.cell
def build_right_panel(mo, lat_slider, lon_slider, weather_radio, prediction_display):
    right_panel = mo.vstack([
        mo.Html("""
<div style="font-family:system-ui,-apple-system,sans-serif;">
  <div style="font-size:10px; font-weight:700; letter-spacing:2px; text-transform:uppercase;
              color:#475569; padding-bottom:10px; border-bottom:1px solid #1e293b; margin-bottom:18px;">
    🧠 Model Predictive Inference
  </div>
  <div style="font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:1px;
              color:#334155; margin-bottom:8px;">Coordinate Buckets</div>
</div>
"""),
        lat_slider,
        lon_slider,
        mo.Html("""
<div style="font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:1px;
            color:#334155; margin-top:10px; margin-bottom:4px;">Meteorological Shift</div>
"""),
        weather_radio,
        prediction_display,
    ], gap=8)
    return right_panel,


@app.cell
def assemble_layout(mo, left_panel, center_panel, right_panel):
    _header = mo.Html("""
<div style="font-family:system-ui,-apple-system,sans-serif; background:#0b1220;
            border-bottom:1px solid #1e293b; padding:13px 24px;
            display:flex; justify-content:space-between; align-items:center;">
  <div style="display:flex; align-items:center; gap:14px;">
    <span style="color:#f1f5f9; font-weight:800; font-size:15px; letter-spacing:0.3px;">
      🇸🇬 SG TRANSIT-WEATHER MESH
    </span>
    <span style="background:#1e293b; border:1px solid #334155; color:#64748b;
                 padding:3px 10px; border-radius:20px; font-size:10px;
                 font-weight:700; letter-spacing:0.5px;">● ACTIVE SESSION</span>
  </div>
  <span style="background:#052e16; border:1px solid #166534; color:#22c55e;
               padding:3px 12px; border-radius:20px; font-size:10px;
               font-weight:700; letter-spacing:0.5px;">⏱️ LIVE DATA SYNC</span>
</div>
""")

    view = mo.vstack([
        _header,
        mo.hstack([left_panel, center_panel, right_panel], align="start", gap=0),
    ], gap=0)
    return view,


@app.cell
def render(view):
    view
    return


if __name__ == "__main__":
    app.run()
