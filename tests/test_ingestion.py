# tests/test_ingestion.py
import pytest
import requests_mock
from dlt.extract.exceptions import ResourceExtractionError
from sg_transit_weather_mesh.utils import load_config
from sg_transit_weather_mesh.assets.ingestion import sg_gov_source

def test_config_layer_loading():
    """Verifies that the YAML parsing utility correctly extracts configuration fields."""
    config = load_config()
    assert "api" in config
    assert "key" in config["api"]
    assert "base_url" in config["api"]
    assert config["api"]["key"].startswith("v2:")

def test_api_ingestion_contract_success():
    """Verifies dlt resource extraction rules handle mock API streams."""
    config = load_config()
    base_url = config["api"]["base_url"]

    mock_taxi_response = {
        "data": {
            "taxi_availability": [
                {"latitude": 1.3521, "longitude": 103.8198, "taxi_id": "TAXI-TEST-99"}
            ]
        }
    }

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}/transport/taxi-availability", json=mock_taxi_response)
        mock.get(f"{base_url}/two-hr-forecast", json={"data": {"items": []}})

        # 1. Instantiate the dlt source instance object
        source = sg_gov_source()
        
        # 2. Extract the actual DltResource object by key lookup from the source map
        taxi_resource = source.resources["taxi_availability"]
        
        # 3. Read raw entries directly using dlt's explicit data-iterator property
        raw_items = list(taxi_resource)

        # 4. Assert against the returned dictionary payload structural schema
        assert len(raw_items) == 1
        extracted_payload = raw_items[0]
        assert "taxi_availability" in extracted_payload
        assert extracted_payload["taxi_availability"][0]["taxi_id"] == "TAXI-TEST-99"

def test_api_ingestion_contract_failure():
    """Ensures our ingestion layers flag errors if the API throws a 500 error."""
    config = load_config()
    base_url = config["api"]["base_url"]

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}/transport/taxi-availability", status_code=500)
        
        # Instantiate the lazy source map configuration
        source = sg_gov_source()
        taxi_resource = source.resources["taxi_availability"]
        
        # The exception triggers exactly when evaluating the resource iterator
        with pytest.raises(ResourceExtractionError):
            list(taxi_resource)
