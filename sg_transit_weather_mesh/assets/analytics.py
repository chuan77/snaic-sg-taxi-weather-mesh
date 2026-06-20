# sg_transit_weather_mesh/assets/analytics.py
import duckdb
from dagster import asset, Output, AssetIn

@asset(
    ins={"ingest_sg_raw_data": AssetIn()},
    compute_kind="duckdb"
)
def analytics_taxi_weather_mart(ingest_sg_raw_data): # 👈 FIXED: Added the argument to match the ins dict key
    """Groups geospatial dimensions into coordinate grids inside DuckDB."""
    # Connect to the persistent DuckDB file engine
    conn = duckdb.connect("data/warehouse.duckdb")
    
    query = """
        CREATE SCHEMA IF NOT EXISTS mart;
        
        CREATE OR REPLACE TABLE mart.fct_taxi_weather_trends AS
        SELECT 
            DATE_TRUNC('hour', CAST(t.timestamp AS TIMESTAMP)) AS event_hour,
            ROUND(t.latitude, 2) AS grid_lat,
            ROUND(t.longitude, 2) AS grid_lon,
            COUNT(t.taxi_id) AS available_taxis_count,
            AVG(w.temperature) AS avg_regional_temperature,
            MAX(w.forecast) AS prominent_weather_condition
        FROM raw.taxi_availability AS t
        LEFT JOIN raw.weather_forecast AS w
          ON DATE_TRUNC('hour', CAST(t.timestamp AS TIMESTAMP)) = DATE_TRUNC('hour', CAST(w.timestamp AS TIMESTAMP))
         AND ROUND(t.latitude, 1) = ROUND(w.latitude, 1)
         AND ROUND(t.longitude, 1) = ROUND(w.longitude, 1)
        GROUP BY 1, 2, 3;
    """
    conn.execute(query)
    metrics = conn.execute("SELECT COUNT(*) FROM mart.fct_taxi_weather_trends").fetchone()
    conn.close()
    
    return Output(value=None, metadata={"total_analytics_rows": metrics})
