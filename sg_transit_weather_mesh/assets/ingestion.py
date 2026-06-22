# sg_transit_weather_mesh/assets/ingestion.py
import dlt
import duckdb
import requests
from datetime import datetime
from pathlib import Path
from dagster import asset, Output
from ..utils import load_config

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_DB_PATH = str(_PROJECT_ROOT / "data" / "warehouse.duckdb")

# v1 API (taxi availability) still uses the key-authenticated endpoint
config = load_config()
_HEADERS_V1 = {"x-api-key": config["api"]["key"]}
_BASE_URL_V1 = config["api"]["base_url"]

# v2 open API — no authentication required
_WEATHER_V2_URL    = "https://api-open.data.gov.sg/v2/real-time/api/two-hr-forecast"
_WEATHER_24H_V2_URL = "https://api-open.data.gov.sg/v2/real-time/api/twenty-four-hr-forecast"


@dlt.source
def sg_gov_source():
    _SG_LAT = (1.1, 1.5)
    _SG_LON = (103.5, 104.1)

    @dlt.resource(write_disposition="append", primary_key=["timestamp", "latitude", "longitude"])
    def taxi_availability():
        """GeoJSON point cloud of all available taxis — one row per coordinate."""
        url = f"{_BASE_URL_V1}/transport/taxi-availability"
        response = requests.get(url, headers=_HEADERS_V1, timeout=30)
        response.raise_for_status()
        data = response.json()
        if not data.get("features"):
            return
        feature = data["features"][0]
        timestamp = feature["properties"]["timestamp"]
        for lon, lat in feature["geometry"]["coordinates"]:
            if not (_SG_LAT[0] <= lat <= _SG_LAT[1] and _SG_LON[0] <= lon <= _SG_LON[1]):
                continue
            yield {"timestamp": timestamp, "latitude": lat, "longitude": lon}

    @dlt.resource(write_disposition="replace", primary_key=["timestamp", "area"])
    def weather_forecast():
        """2-hour area forecast from NEA via the data.gov.sg v2 open API.

        Response shape (v2):
          { code: 0,
            data: {
              area_metadata: [{name, label_location: {latitude, longitude}}],
              items: [{
                timestamp, update_timestamp,
                valid_period: {start, end, text},
                forecasts: [{area, forecast}]
              }]
            }
          }
        """
        response = requests.get(_WEATHER_V2_URL, timeout=30)
        response.raise_for_status()
        payload = response.json()

        if payload.get("code") != 0:
            raise ValueError(
                f"data.gov.sg v2 API error: {payload.get('errorMsg', 'unknown')}"
            )

        data = payload["data"]
        area_locations = {
            m["name"]: m["label_location"]
            for m in data["area_metadata"]
        }
        item = data["items"][0]
        timestamp = item["timestamp"]
        update_timestamp = item["update_timestamp"]
        valid_period = item["valid_period"]

        for entry in item["forecasts"]:
            area = entry["area"]
            loc = area_locations.get(area, {})
            yield {
                "timestamp": timestamp,
                "update_timestamp": update_timestamp,
                "valid_period_start": valid_period["start"],
                "valid_period_end": valid_period["end"],
                "valid_period_text": valid_period["text"],
                "area": area,
                "forecast": entry["forecast"],
                "latitude": loc.get("latitude"),
                "longitude": loc.get("longitude"),
            }

    @dlt.resource(name="weather_forecast_24hr", write_disposition="replace",
                  primary_key=["fetched_at", "period_text", "region"])
    def weather_forecast_24hr():
        """24-hour regional forecast from NEA via the data.gov.sg v2 open API.

        Yields one row per (period × region) combination so the mart can query
        by period label or region without JSON parsing.
        """
        resp = requests.get(_WEATHER_24H_V2_URL, timeout=30)
        resp.raise_for_status()
        records = resp.json().get("data", {}).get("records", [])
        if not records:
            return
        rec = records[0]
        fetched_at       = rec.get("updatedTimestamp", datetime.utcnow().isoformat())
        valid_start      = rec.get("validPeriod", {}).get("start", "")
        valid_end        = rec.get("validPeriod", {}).get("end", "")
        general_forecast = rec.get("general", {}).get("forecast", {}).get("summary", "")
        temp_low         = rec.get("general", {}).get("temperature", {}).get("low", 0)
        temp_high        = rec.get("general", {}).get("temperature", {}).get("high", 0)
        rh_low           = rec.get("general", {}).get("relativeHumidity", {}).get("low", 0)
        rh_high          = rec.get("general", {}).get("relativeHumidity", {}).get("high", 0)
        for period in rec.get("periods", []):
            period_text  = period.get("timePeriod", {}).get("text", "")
            period_start = period.get("timePeriod", {}).get("start", "")
            period_end   = period.get("timePeriod", {}).get("end", "")
            for region, rdata in period.get("regions", {}).items():
                yield {
                    "fetched_at":       fetched_at,
                    "valid_start":      valid_start,
                    "valid_end":        valid_end,
                    "general_forecast": general_forecast,
                    "temp_low":         temp_low,
                    "temp_high":        temp_high,
                    "rh_low":           rh_low,
                    "rh_high":          rh_high,
                    "period_text":      period_text,
                    "period_start":     period_start,
                    "period_end":       period_end,
                    "region":           region,
                    "forecast":         rdata.get("forecast", ""),
                }

    return taxi_availability, weather_forecast, weather_forecast_24hr


@asset(compute_kind="dlt")
def ingest_sg_raw_data():
    """Ingests taxi availability (v1) and 2-hr weather forecast (v2) into DuckDB raw schema."""
    pipeline = dlt.pipeline(
        pipeline_name="sg_transport_weather",
        destination=dlt.destinations.duckdb(credentials=_DB_PATH),
        dataset_name="raw",
    )
    load_info = pipeline.run(sg_gov_source())

    conn = duckdb.connect(_DB_PATH, read_only=True)
    try:
        rows_total = conn.execute(
            "SELECT COUNT(*) FROM raw.taxi_availability"
        ).fetchone()[0]
        rows_valid = conn.execute("""
            SELECT COUNT(*) FROM raw.taxi_availability
            WHERE latitude  BETWEEN 1.1 AND 1.5
              AND longitude BETWEEN 103.5 AND 104.1
        """).fetchone()[0]
    finally:
        conn.close()

    return Output(
        value=None,
        metadata={
            "dlt_load_summary":  str(load_info),
            "rows_total":        rows_total,
            "rows_in_bounds":    rows_valid,
            "rows_filtered_pct": round((1 - rows_valid / rows_total) * 100, 2) if rows_total else 0,
        },
    )
