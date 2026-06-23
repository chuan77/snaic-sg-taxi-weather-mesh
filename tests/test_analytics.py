# tests/test_analytics.py
import pytest
import duckdb

@pytest.fixture
def in_memory_warehouse():
    """Initializes a clean, sandboxed DuckDB space for running SQL grid transformations."""
    conn = duckdb.connect(":memory:")

    conn.execute("CREATE SCHEMA raw;")
    conn.execute("""
        CREATE TABLE raw.taxi_availability (
            timestamp VARCHAR, latitude DOUBLE, longitude DOUBLE
        );
    """)
    conn.execute("""
        CREATE TABLE raw.weather_forecast (
            timestamp VARCHAR, area VARCHAR, forecast VARCHAR,
            latitude DOUBLE, longitude DOUBLE
        );
    """)

    # Both taxis round down to the same 1.35, 103.82 grid block
    conn.execute("""
        INSERT INTO raw.taxi_availability VALUES
        ('2026-06-21T01:00:00+08:00', 1.3521, 103.8198),
        ('2026-06-21T01:05:00+08:00', 1.3544, 103.8211);
    """)

    # Bishan label_location rounds to the same 0.1-degree cell as the taxis above
    conn.execute("""
        INSERT INTO raw.weather_forecast VALUES
        ('2026-06-21T01:00:00+08:00', 'Bishan', 'Passing Showers', 1.350772, 103.839);
    """)

    yield conn
    conn.close()

def test_geospatial_grid_clustering(in_memory_warehouse):
    """Verifies that point coordinates resolve correctly into localized spatial grids."""
    conn = in_memory_warehouse

    conn.execute("CREATE SCHEMA IF NOT EXISTS mart;")
    conn.execute("""
        CREATE TABLE mart.fct_taxi_weather_trends AS
        SELECT
            DATE_TRUNC('hour', CAST(t.timestamp AS TIMESTAMP)) AS event_hour,
            ROUND(t.latitude, 2) AS grid_lat,
            ROUND(t.longitude, 2) AS grid_lon,
            COUNT(*) AS available_taxis_count,
            MAX(w.forecast) AS prominent_weather_condition
        FROM raw.taxi_availability AS t
        LEFT JOIN raw.weather_forecast AS w
          ON DATE_TRUNC('hour', CAST(t.timestamp AS TIMESTAMP)) = DATE_TRUNC('hour', CAST(w.timestamp AS TIMESTAMP))
         AND ROUND(t.latitude, 1) = ROUND(w.latitude, 1)
         AND ROUND(t.longitude, 1) = ROUND(w.longitude, 1)
        GROUP BY 1, 2, 3;
    """)

    results = conn.execute("SELECT * FROM mart.fct_taxi_weather_trends").fetchall()

    assert len(results) == 1
    record = results[0]
    assert record[1] == 1.35                     # grid_lat
    assert record[2] == 103.82                   # grid_lon
    assert record[3] == 2                        # available_taxis_count
    assert record[4] == "Passing Showers"        # prominent_weather_condition

def test_geospatial_grid_no_weather_match(in_memory_warehouse):
    """Verifies taxis with no matching weather area still appear in the mart with NULL forecast."""
    conn = in_memory_warehouse

    # Insert a taxi far outside any weather area's 0.1-degree cell
    conn.execute("INSERT INTO raw.taxi_availability VALUES ('2026-06-21T01:00:00+08:00', 1.20, 103.60);")

    conn.execute("CREATE SCHEMA IF NOT EXISTS mart;")
    conn.execute("""
        CREATE TABLE mart.fct_taxi_weather_trends AS
        SELECT
            DATE_TRUNC('hour', CAST(t.timestamp AS TIMESTAMP)) AS event_hour,
            ROUND(t.latitude, 2) AS grid_lat,
            ROUND(t.longitude, 2) AS grid_lon,
            COUNT(*) AS available_taxis_count,
            MAX(w.forecast) AS prominent_weather_condition
        FROM raw.taxi_availability AS t
        LEFT JOIN raw.weather_forecast AS w
          ON DATE_TRUNC('hour', CAST(t.timestamp AS TIMESTAMP)) = DATE_TRUNC('hour', CAST(w.timestamp AS TIMESTAMP))
         AND ROUND(t.latitude, 1) = ROUND(w.latitude, 1)
         AND ROUND(t.longitude, 1) = ROUND(w.longitude, 1)
        GROUP BY 1, 2, 3;
    """)

    results = conn.execute(
        "SELECT * FROM mart.fct_taxi_weather_trends WHERE grid_lat = 1.20"
    ).fetchall()

    assert len(results) == 1
    assert results[0][3] == 1        # available_taxis_count
    assert results[0][4] is None     # no weather match → NULL forecast

def test_analytics_asset_metadata_is_int(tmp_path, monkeypatch):
    """Regression: analytics asset must emit an int for total_analytics_rows, not a tuple.

    fetchone() returns (n,) — passing that tuple raw to Dagster Output metadata raises
    DagsterInvalidMetadata. This test catches that class of mistake.
    """
    import duckdb as _duckdb
    from sg_transit_weather_mesh.assets.analytics import analytics_taxi_weather_mart

    db_path = str(tmp_path / "warehouse.duckdb")
    conn = _duckdb.connect(db_path)
    conn.execute("CREATE SCHEMA raw;")
    conn.execute("CREATE TABLE raw.taxi_availability (timestamp VARCHAR, latitude DOUBLE, longitude DOUBLE);")
    conn.execute("CREATE TABLE raw.weather_forecast (timestamp VARCHAR, area VARCHAR, forecast VARCHAR, latitude DOUBLE, longitude DOUBLE);")
    conn.execute("INSERT INTO raw.taxi_availability VALUES ('2026-06-21T01:00:00+08:00', 1.35, 103.82);")
    conn.close()

    _original_connect = _duckdb.connect
    monkeypatch.setattr(_duckdb, "connect", lambda *_: _original_connect(db_path))

    output = analytics_taxi_weather_mart(ingest_sg_raw_data=None)
    row_count = output.metadata["total_analytics_rows"].value
    assert isinstance(row_count, int), f"Expected int, got {type(row_count)}"
    assert row_count == 1


def test_make_cluster_run_name_is_deterministic():
    """Same fetched_at value must always produce the same run name string."""
    from sg_transit_weather_mesh.assets.analytics import _make_cluster_run_name
    ts = "2024-06-23 10:00:00"
    assert _make_cluster_run_name(ts) == _make_cluster_run_name(ts)
    assert _make_cluster_run_name(ts).startswith("dbscan_")
    assert _make_cluster_run_name(ts) != _make_cluster_run_name("2024-06-23 10:05:00")


def test_make_cluster_run_name_with_none_falls_back():
    """None fetched_at must still produce a valid non-empty string."""
    from sg_transit_weather_mesh.assets.analytics import _make_cluster_run_name
    name = _make_cluster_run_name(None)
    assert isinstance(name, str) and len(name) > 0


def test_make_forecast_run_name_is_deterministic():
    """Same fetched_at value must always produce the same GBR run name."""
    from sg_transit_weather_mesh.assets.analytics import _make_forecast_run_name
    ts = "2024-06-23 10:00:00"
    assert _make_forecast_run_name(ts) == _make_forecast_run_name(ts)
    assert _make_forecast_run_name(ts).startswith("gbr_")
    assert _make_forecast_run_name(ts) != _make_forecast_run_name("2024-06-23 10:05:00")


def test_make_forecast_run_name_with_none_falls_back():
    """None fetched_at must still produce a valid non-empty string."""
    from sg_transit_weather_mesh.assets.analytics import _make_forecast_run_name
    name = _make_forecast_run_name(None)
    assert isinstance(name, str) and len(name) > 0
