# tests/test_ingestion.py
import pytest
import requests_mock
import dlt
from dlt.extract.exceptions import ResourceExtractionError
from sg_transit_weather_mesh.utils import load_config
from sg_transit_weather_mesh.assets.ingestion import (
    sg_gov_source,
    ingest_sg_raw_data,
    _WEATHER_V2_URL,
)

MOCK_TAXI_RESPONSE = {
    "type": "FeatureCollection",
    "features": [{
        "type": "Feature",
        "geometry": {
            "type": "MultiPoint",
            "coordinates": [[103.8198, 1.3521]],
        },
        "properties": {
            "timestamp": "2026-06-21T08:00:00+08:00",
            "taxi_count": 1,
            "api_info": {"status": "healthy"},
        },
    }],
}

# v2 API response shape: wrapped in {"code": 0, "data": {...}, "errorMsg": null}
MOCK_WEATHER_RESPONSE_V2 = {
    "code": 0,
    "data": {
        "area_metadata": [
            {"name": "Bishan", "label_location": {"latitude": 1.350772, "longitude": 103.839}}
        ],
        "items": [{
            "timestamp": "2026-06-21T08:00:00+08:00",
            "update_timestamp": "2026-06-21T08:05:00+08:00",
            "valid_period": {
                "start": "2026-06-21T08:00:00+08:00",
                "end": "2026-06-21T10:00:00+08:00",
                "text": "8.00 am to 10.00 am",
            },
            "forecasts": [{"area": "Bishan", "forecast": "Partly Cloudy (Day)"}],
        }],
    },
    "errorMsg": None,
}


def test_config_layer_loading():
    """Verifies that the YAML parsing utility correctly extracts configuration fields."""
    config = load_config()
    assert "api" in config
    assert "key" in config["api"]
    assert "base_url" in config["api"]
    assert config["api"]["key"].startswith("v2:")


def test_weather_v2_url_is_open_api():
    """Verifies the v2 weather URL points to the open API (no /v1 or key requirement)."""
    assert "api-open.data.gov.sg" in _WEATHER_V2_URL
    assert "/v2/real-time/api/two-hr-forecast" in _WEATHER_V2_URL


def test_api_ingestion_contract_success():
    """Verifies taxi_availability yields one flat row per coordinate with timestamp, lat, lon."""
    config = load_config()
    base_url = config["api"]["base_url"]

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}/transport/taxi-availability", json=MOCK_TAXI_RESPONSE)
        mock.get(_WEATHER_V2_URL, json=MOCK_WEATHER_RESPONSE_V2)

        source = sg_gov_source()
        raw_items = list(source.resources["taxi_availability"])

        assert len(raw_items) == 1
        record = raw_items[0]
        assert record["latitude"] == 1.3521
        assert record["longitude"] == 103.8198
        assert record["timestamp"] == "2026-06-21T08:00:00+08:00"


def test_weather_resource_yields_flat_rows_with_area_coordinates():
    """Verifies weather_forecast joins forecasts with area_metadata and yields one row per area
    including all v2 valid_period fields."""
    config = load_config()
    base_url = config["api"]["base_url"]

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}/transport/taxi-availability", json=MOCK_TAXI_RESPONSE)
        mock.get(_WEATHER_V2_URL, json=MOCK_WEATHER_RESPONSE_V2)

        source = sg_gov_source()
        raw_items = list(source.resources["weather_forecast"])

        assert len(raw_items) == 1
        record = raw_items[0]
        assert record["area"] == "Bishan"
        assert record["forecast"] == "Partly Cloudy (Day)"
        assert record["latitude"] == 1.350772
        assert record["longitude"] == 103.839
        assert record["timestamp"] == "2026-06-21T08:00:00+08:00"
        assert record["update_timestamp"] == "2026-06-21T08:05:00+08:00"
        assert record["valid_period_start"] == "2026-06-21T08:00:00+08:00"
        assert record["valid_period_end"] == "2026-06-21T10:00:00+08:00"
        assert record["valid_period_text"] == "8.00 am to 10.00 am"


def test_weather_resource_rejects_non_zero_api_code():
    """Verifies that a v2 API error code (non-zero) raises ValueError."""
    config = load_config()
    base_url = config["api"]["base_url"]

    error_response = {"code": 1, "data": None, "errorMsg": "Internal server error"}

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}/transport/taxi-availability", json=MOCK_TAXI_RESPONSE)
        mock.get(_WEATHER_V2_URL, json=error_response)

        source = sg_gov_source()
        with pytest.raises(ResourceExtractionError):
            list(source.resources["weather_forecast"])


def test_multiple_coordinates_yield_multiple_taxi_rows():
    """Verifies that a response with N coordinates produces exactly N ingested rows."""
    config = load_config()
    base_url = config["api"]["base_url"]

    multi_coord_response = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {
                "type": "MultiPoint",
                "coordinates": [[103.82, 1.35], [103.83, 1.36], [103.84, 1.37]],
            },
            "properties": {
                "timestamp": "2026-06-21T08:00:00+08:00",
                "taxi_count": 3,
                "api_info": {"status": "healthy"},
            },
        }],
    }

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}/transport/taxi-availability", json=multi_coord_response)
        mock.get(_WEATHER_V2_URL, json=MOCK_WEATHER_RESPONSE_V2)

        source = sg_gov_source()
        raw_items = list(source.resources["taxi_availability"])
        assert len(raw_items) == 3


def test_api_ingestion_contract_failure():
    """Ensures our ingestion layers flag errors if the API throws a 500 error."""
    config = load_config()
    base_url = config["api"]["base_url"]

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}/transport/taxi-availability", status_code=500)

        source = sg_gov_source()
        with pytest.raises(ResourceExtractionError):
            list(source.resources["taxi_availability"])


def test_pipeline_rejects_credentials_kwarg():
    """Regression: dlt.pipeline() does not accept credentials; it belongs on the destination factory."""
    with pytest.raises(TypeError, match="credentials"):
        dlt.pipeline(
            pipeline_name="test",
            destination="duckdb",
            credentials="some/path.duckdb",
        )


def test_pipeline_construction_accepts_valid_args(tmp_path):
    """Ensures dlt.pipeline() is called with a destination object carrying credentials, not a bare kwarg."""
    db_path = str(tmp_path / "warehouse.duckdb")
    pipeline = dlt.pipeline(
        pipeline_name="sg_transport_weather",
        destination=dlt.destinations.duckdb(credentials=db_path),
        dataset_name="raw",
    )
    assert pipeline.pipeline_name == "sg_transport_weather"
    assert pipeline.dataset_name == "raw"


def test_ingest_asset_runs_end_to_end(tmp_path, monkeypatch):
    """Smoke-tests the full Dagster asset: pipeline construction and run against a temp DuckDB."""
    config = load_config()
    base_url = config["api"]["base_url"]

    db_path = str(tmp_path / "warehouse.duckdb")
    original_pipeline = dlt.pipeline

    def _pipeline_redirected_to_tmp(**kwargs):
        kwargs["destination"] = dlt.destinations.duckdb(credentials=db_path)
        return original_pipeline(**kwargs)

    monkeypatch.setattr(dlt, "pipeline", _pipeline_redirected_to_tmp)

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}/transport/taxi-availability", json=MOCK_TAXI_RESPONSE)
        mock.get(_WEATHER_V2_URL, json=MOCK_WEATHER_RESPONSE_V2)
        result = ingest_sg_raw_data()

    assert result is not None
