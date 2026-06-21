# sg_transit_weather_mesh/assets/ingestion.py
import dlt
import requests
from dagster import asset, Output
from ..utils import load_config

# Resolves parameters seamlessly from config/config.yaml
config = load_config()
HEADERS = {"x-api-key": config["api"]["key"]}
BASE_URL = config["api"]["base_url"]

@dlt.source
def sg_gov_source():
    @dlt.resource(write_disposition="append")
    def taxi_availability():
        url = f"{BASE_URL}/transport/taxi-availability"
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        data = response.json()
        feature = data["features"][0]
        timestamp = feature["properties"]["timestamp"]
        for lon, lat in feature["geometry"]["coordinates"]:
            yield {"timestamp": timestamp, "latitude": lat, "longitude": lon}

    @dlt.resource(write_disposition="replace")
    def weather_forecast():
        url = f"{BASE_URL}/environment/2-hour-weather-forecast"
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        data = response.json()
        area_locations = {
            m["name"]: m["label_location"]
            for m in data["area_metadata"]
        }
        item = data["items"][0]
        timestamp = item["timestamp"]
        for entry in item["forecasts"]:
            area = entry["area"]
            loc = area_locations.get(area, {})
            yield {
                "timestamp": timestamp,
                "area": area,
                "forecast": entry["forecast"],
                "latitude": loc.get("latitude"),
                "longitude": loc.get("longitude"),
            }

    return taxi_availability, weather_forecast

@asset(compute_kind="dlt")
def ingest_sg_raw_data():
    """Ingests API matrices utilizing configurations established inside the config directory."""
    pipeline = dlt.pipeline(
        pipeline_name="sg_transport_weather",
        destination=dlt.destinations.duckdb(credentials="data/warehouse.duckdb"),
        dataset_name="raw"
    )
    load_info = pipeline.run(sg_gov_source())
    return Output(value=None, metadata={"dlt_load_summary": str(load_info)})
