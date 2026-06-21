# sg_transit_weather_mesh/notebooks/dashboard.py
import marimo as __marimo

app = __marimo.App(width="full")


@app.cell
def init_libraries():
    import marimo as mo
    import duckdb
    import pandas as pd
    import plotly.express as px
    import os
    import yaml
    return duckdb, mo, os, pd, px, yaml


@app.cell
def load_directory_configurations(os, yaml):
    # Crawl up out of sg_transit_weather_mesh/notebooks to the main workspace root
    root_dir = os.path.abspath(os.path.join(os.getcwd(), "../../"))
    config_path = os.path.join(root_dir, "config", "config.yaml")
    db_path = os.path.join(root_dir, "data", "warehouse.duckdb")
    
    # Fallback checkpoint handling if notebook is initialized from the root workspace folder directly
    if not os.path.exists(config_path):
        root_dir = os.path.abspath(os.getcwd())
        config_path = os.path.join(root_dir, "config", "config.yaml")
        db_path = os.path.join(root_dir, "data", "warehouse.duckdb")

    with open(config_path, "r") as file:
        config_data = yaml.safe_load(file)
        
    return db_path, config_data


@app.cell
def connect_data_warehouse(db_path, duckdb):
    # Secure clean transactional read-only link into the compiled database
    conn = duckdb.connect(db_path, read_only=True)
    return conn


@app.cell
def extract_warehouse_metrics(conn, pd):
    try:
        df_trends = conn.execute("""
            SELECT event_hour, grid_lat, grid_lon, available_taxis_count,
                   prominent_weather_condition
            FROM mart.fct_taxi_weather_trends
            ORDER BY event_hour DESC
        """).df()
    except Exception:
        df_trends = pd.DataFrame([{
            "event_hour": pd.Timestamp.now(), "grid_lat": 1.35, "grid_lon": 103.82,
            "available_taxis_count": 0,
            "prominent_weather_condition": "Awaiting Database Generation"
        }])
    return df_trends


@app.cell
def pipeline_transform_kpis(df_trends):
    total_active_taxis = df_trends["available_taxis_count"].sum()
    top_condition = df_trends["prominent_weather_condition"].mode().head(1).values if not df_trends.empty else "N/A"
    return top_condition, total_active_taxis


@app.cell
def build_ui_dashlets(mo, top_condition, total_active_taxis):
    kpi_total_taxis = mo.stat(value=f"{total_active_taxis:,}", label="Active Fleet Density")
    kpi_monsoon = mo.stat(value=str(top_condition), label="Prevalent Weather Mode")

    dashlet_row = mo.hstack([kpi_total_taxis, kpi_monsoon], justify="space-between")
    return dashlet_row, kpi_monsoon, kpi_total_taxis


@app.cell
def build_geospatial_heatmap(df_trends, px):
    if not df_trends.empty and df_trends["available_taxis_count"].sum() > 0:
        fig = px.density_map(
            df_trends, lat="grid_lat", lon="grid_lon", z="available_taxis_count", radius=25,
            center=dict(lat=1.3521, lon=103.8198), zoom=10.8,
            map_style="carto-darkmatter", title="Live Regional Density Map Layer (From DuckDB Grid)",
            hover_data=["prominent_weather_condition"]
        )
        fig.update_layout(margin={"r":0,"t":40,"l":0,"b":0}, paper_bgcolor="#0f172a")
    else:
        fig = px.scatter_map(lat=[1.3521], lon=[103.8198], zoom=10.5, map_style="carto-darkmatter", title="Awaiting Data Synchronization...")
        fig.update_layout(margin={"r":0,"t":40,"l":0,"b":0})
    return fig


@app.cell
def assemble_application_viewport(dashlet_row, fig, mo):
    view = mo.vstack([
        mo.md("# 🇸🇬 Singapore Transit & Weather Mesh Data System"),
        mo.md("### 📊 Warehouse Mart Metrics (`mart.fct_taxi_weather_trends`)"),
        dashlet_row,
        mo.md("---"),
        mo.ui.plotly(fig)
    ], gap=1.5)
    return view


@app.cell
def render_output_view(view):
    view
    return


if __name__ == "__main__":
    app.run()
