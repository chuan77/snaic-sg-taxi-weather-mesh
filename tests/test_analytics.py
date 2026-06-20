# tests/test_analytics.py
import pytest
import duckdb

@pytest.fixture
def in_memory_warehouse():
    """Initializes a clean, sandboxed DuckDB space for running SQL grid transformations."""
    conn = duckdb.connect(":memory:")
    
    # 1. Establish the clean landing environment
    conn.execute("CREATE SCHEMA raw;")
    conn.execute("""
        CREATE TABLE raw.taxi_availability (
            timestamp VARCHAR, latitude DOUBLE, longitude DOUBLE, taxi_id VARCHAR
        );
    """)
    conn.execute("""
        CREATE TABLE raw.weather_forecast (
            timestamp VARCHAR, latitude DOUBLE, longitude DOUBLE, temperature DOUBLE, forecast VARCHAR
        );
    """)
    
    # 2. Insert precise test data to check our rounding rules
    # Both points should round down to the same 1.35, 103.82 grid block
    conn.execute("""
        INSERT INTO raw.taxi_availability VALUES 
        ('2026-06-21T01:00:00+08:00', 1.3521, 103.8198, 'TAXI-A'),
        ('2026-06-21T01:05:00+08:00', 1.3544, 103.8211, 'TAXI-B');
    """)
    
    conn.execute("""
        INSERT INTO raw.weather_forecast VALUES 
        ('2026-06-21T01:00:00+08:00', 1.35, 103.82, 28.5, 'Passing Showers');
    """)
    
    yield conn
    conn.close()

def test_geospatial_grid_clustering(in_memory_warehouse):
    """Verifies that point coordinates resolve correctly into localized spatial grids."""
    conn = in_memory_warehouse
    
    # Execute the exact SQL logic used in our analytics asset module
    conn.execute("CREATE SCHEMA IF NOT EXISTS mart;")
    conn.execute("""
        CREATE TABLE mart.fct_taxi_weather_trends AS
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
    """)
    
    # Check that our metrics aggregated as expected
    results = conn.execute("SELECT * FROM mart.fct_taxi_weather_trends").fetchall()
    
    # Both test taxis should have been grouped into a single spatial coordinate block
    assert len(results) == 1
    
    record = results[0]
    assert record[1] == 1.35                      # grid_lat output matches rounding rules
    assert record[2] == 103.82                    # grid_lon output matches rounding rules
    assert record[3] == 2                         # available_taxis_count matches total inputs
    assert record[4] == 28.5                      # temperature values map cleanly
    assert record[5] == "Passing Showers"         # forecast text aligns correctly
