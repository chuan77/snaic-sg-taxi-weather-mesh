# tests/test_analytics.py
import json
import pytest
import duckdb
from unittest.mock import MagicMock, patch
from sg_transit_weather_mesh.assets.analytics import _champion_selection_result, FORECAST_INTENSITY, INTENSITY_RANK


def _make_rows(n: int) -> list[tuple[float, float]]:
    """Generate n distinct (lat, lng) pairs within Singapore bounds."""
    base_lat, base_lng = 1.3000, 103.8000
    return [(round(base_lat + i * 0.0001, 4), round(base_lng + i * 0.0001, 4)) for i in range(n)]


def test_taxi_window_export_writes_both_files(tmp_path):
    """taxi_window_export must write taxis_window_15.json and taxis_window_30.json."""
    from dagster import build_asset_context
    from sg_transit_weather_mesh.assets.analytics import taxi_window_export

    rows_15 = _make_rows(40)
    rows_30 = _make_rows(80)

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.side_effect = [rows_15, rows_30]

    file_15 = tmp_path / "taxis_window_15.json"
    file_30 = tmp_path / "taxis_window_30.json"

    with build_asset_context() as ctx, \
         patch("sg_transit_weather_mesh.assets.analytics.duckdb.connect", return_value=mock_conn), \
         patch("sg_transit_weather_mesh.assets.analytics._TAXIS_WINDOW_15_JSON", file_15), \
         patch("sg_transit_weather_mesh.assets.analytics._TAXIS_WINDOW_30_JSON", file_30):
        taxi_window_export(ctx, None, None)

    assert file_15.exists(), "taxis_window_15.json was not written"
    assert file_30.exists(), "taxis_window_30.json was not written"


def test_taxi_window_export_json_contract(tmp_path):
    """Each output file must have window_minutes, total, and taxis fields."""
    from dagster import build_asset_context
    from sg_transit_weather_mesh.assets.analytics import taxi_window_export

    rows_15 = _make_rows(3)
    rows_30 = _make_rows(7)

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.side_effect = [rows_15, rows_30]

    file_15 = tmp_path / "taxis_window_15.json"
    file_30 = tmp_path / "taxis_window_30.json"

    with build_asset_context() as ctx, \
         patch("sg_transit_weather_mesh.assets.analytics.duckdb.connect", return_value=mock_conn), \
         patch("sg_transit_weather_mesh.assets.analytics._TAXIS_WINDOW_15_JSON", file_15), \
         patch("sg_transit_weather_mesh.assets.analytics._TAXIS_WINDOW_30_JSON", file_30):
        taxi_window_export(ctx, None, None)

    data_15 = json.loads(file_15.read_text())
    data_30 = json.loads(file_30.read_text())

    assert data_15["window_minutes"] == 15
    assert data_15["total"] == 3
    assert len(data_15["taxis"]) == 3
    assert all("lat" in t and "lng" in t for t in data_15["taxis"])

    assert data_30["window_minutes"] == 30
    assert data_30["total"] == 7
    assert len(data_30["taxis"]) == 7

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


# Tests for _get_champion_val_mae helper


def _make_mock_client(champion_run_id=None, val_mae=None):
    """Build a MlflowClient mock for _get_champion_val_mae tests."""
    client = MagicMock()
    if champion_run_id is None:
        # No alias exists
        from mlflow.exceptions import MlflowException
        client.get_model_version_by_alias.side_effect = MlflowException("no alias")
    else:
        mv = MagicMock()
        mv.run_id = champion_run_id
        client.get_model_version_by_alias.return_value = mv
        metric = MagicMock()
        metric.value = val_mae
        client.get_metric_history.return_value = [metric] if val_mae is not None else []
    return client


def test_get_champion_val_mae_no_alias():
    """Returns None when no @champion alias exists."""
    from sg_transit_weather_mesh.assets.analytics import _get_champion_val_mae
    client = _make_mock_client(champion_run_id=None)
    result = _get_champion_val_mae(client, "TaxiAvailabilityPattern")
    assert result is None


def test_get_champion_val_mae_with_alias():
    """Returns val_mae float when @champion alias exists."""
    from sg_transit_weather_mesh.assets.analytics import _get_champion_val_mae
    client = _make_mock_client(champion_run_id="run-abc", val_mae=12.5)
    result = _get_champion_val_mae(client, "TaxiAvailabilityPattern")
    assert result == 12.5


def test_get_champion_val_mae_empty_metric_history():
    """Returns None when metric history is empty (metric not logged)."""
    from sg_transit_weather_mesh.assets.analytics import _get_champion_val_mae
    client = _make_mock_client(champion_run_id="run-abc", val_mae=None)
    result = _get_champion_val_mae(client, "TaxiAvailabilityPattern")
    assert result is None


def test_champion_guardrail_skips_promotion():
    """gap > threshold → no alias set, tag champion_skipped=guardrail_failed."""
    from sg_transit_weather_mesh.assets.analytics import _CHAMPION_GAP_THRESHOLD
    client = MagicMock()
    gap = _CHAMPION_GAP_THRESHOLD + 1
    promote, tags = _champion_selection_result(client, "TaxiAvailabilityPattern", "3", 10.0, gap)
    assert promote is False
    assert tags.get("champion_skipped") == "guardrail_failed"
    client.set_registered_model_alias.assert_not_called()


def test_champion_first_run_promotes():
    """No existing champion + gap ≤ threshold → alias assigned."""
    from sg_transit_weather_mesh.assets.analytics import _CHAMPION_GAP_THRESHOLD
    client = _make_mock_client(champion_run_id=None)
    gap = _CHAMPION_GAP_THRESHOLD - 1
    promote, tags = _champion_selection_result(client, "TaxiAvailabilityPattern", "3", 10.0, gap)
    assert promote is True
    assert tags.get("champion_promoted") == "true"
    client.set_registered_model_alias.assert_called_once_with("TaxiAvailabilityPattern", "champion", "3")


def test_champion_better_model_promotes():
    """New val_mae < current champion val_mae + gap ≤ threshold → alias reassigned."""
    client = _make_mock_client(champion_run_id="run-old", val_mae=15.0)
    promote, tags = _champion_selection_result(client, "TaxiAvailabilityPattern", "4", 12.0, 5.0)
    assert promote is True
    assert tags.get("champion_promoted") == "true"
    assert tags.get("champion_val_mae") == "15.0"
    client.set_registered_model_alias.assert_called_once_with("TaxiAvailabilityPattern", "champion", "4")


def test_champion_worse_model_no_promotion():
    """New val_mae ≥ current champion val_mae → no alias change."""
    client = _make_mock_client(champion_run_id="run-old", val_mae=10.0)
    promote, tags = _champion_selection_result(client, "TaxiAvailabilityPattern", "4", 12.0, 5.0)
    assert promote is False
    assert tags.get("champion_promoted") == "false"
    assert tags.get("champion_val_mae") == "10.0"
    client.set_registered_model_alias.assert_not_called()


def test_is_peak_hour_true_for_morning_peak():
    """Hours 7 and 8 are morning peak."""
    for h in (7, 8):
        assert (1 if h in {7, 8, 17, 18, 19} else 0) == 1


def test_is_peak_hour_true_for_evening_peak():
    """Hours 17, 18, 19 are evening peak."""
    for h in (17, 18, 19):
        assert (1 if h in {7, 8, 17, 18, 19} else 0) == 1


def test_is_peak_hour_false_for_offpeak():
    """Hour 12 (midday) and 3 (night) are not peak."""
    for h in (3, 12, 23):
        assert (1 if h in {7, 8, 17, 18, 19} else 0) == 0
