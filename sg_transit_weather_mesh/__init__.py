from dagster import Definitions, load_assets_from_modules, define_asset_job, ScheduleDefinition
from .assets import ingestion, analytics
from .utils import load_config

config = load_config()
cron_interval = config["orchestration"].get("poll_cron_schedule", "*/5 * * * *")
retrain_cron = config["orchestration"].get("forecast_retrain_cron_schedule", "0 * * * *")

all_assets = load_assets_from_modules([ingestion, analytics])

# 5-minute realtime sync — all assets except demand_forecast_export
pipeline_execution_job = define_asset_job(
    name="sg_taxi_weather_sync_job",
    selection=[
        "ingest_sg_raw_data",
        "analytics_taxi_weather_mart",
        "weather_nowcast_export",
        "hotspots_export",
        "taxis_export",
        "taxi_window_export",
        "surge_predictor_export",
        "taxi_clusters_export",
        "weather_24hr_export",
        "chat_context_export",
        "subzones_export",
    ],
)

# Hourly GBR retraining — runs against already-populated warehouse.duckdb
demand_forecast_job = define_asset_job(
    name="demand_forecast_job",
    selection=["demand_forecast_export"],
)

realtime_api_poll_schedule = ScheduleDefinition(
    name="data_gov_sg_realtime_poll_schedule",
    job=pipeline_execution_job,
    cron_schedule=cron_interval,
    execution_timezone="Asia/Singapore",
)

demand_forecast_retrain_schedule = ScheduleDefinition(
    name="demand_forecast_retrain_schedule",
    job=demand_forecast_job,
    cron_schedule=retrain_cron,
    execution_timezone="Asia/Singapore",
)

defs = Definitions(
    assets=all_assets,
    jobs=[pipeline_execution_job, demand_forecast_job],
    schedules=[realtime_api_poll_schedule, demand_forecast_retrain_schedule],
)
