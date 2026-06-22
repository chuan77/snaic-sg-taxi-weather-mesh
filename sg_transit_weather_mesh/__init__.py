# sg_transit_weather_mesh/__init__.py
from dagster import Definitions, load_assets_from_modules, define_asset_job, ScheduleDefinition
from .assets import ingestion, analytics
from .utils import load_config

# 1. Load pipeline configurations
config = load_config()
cron_interval = config["orchestration"].get("poll_cron_schedule", "*/5 * * * *")

# 2. Gather code-defined assets into the workspace graph
all_assets = load_assets_from_modules([ingestion, analytics])

# 3. Corrected Function Name: define_asset_job (lowercase)
pipeline_execution_job = define_asset_job(
    name="sg_taxi_weather_sync_job",
    selection=["ingest_sg_raw_data", "analytics_taxi_weather_mart", "weather_nowcast_export", "hotspots_export", "taxis_export", "surge_predictor_export", "taxi_clusters_export", "weather_24hr_export", "demand_forecast_export", "chat_context_export", "subzones_export"]
)

# 4. Bind the Job to a cron schedule dynamically derived from config.yaml
realtime_api_poll_schedule = ScheduleDefinition(
    name="data_gov_sg_realtime_poll_schedule",
    job=pipeline_execution_job,
    cron_schedule=cron_interval,
    execution_timezone="Asia/Singapore"
)

# 5. Export unified manifest to the Dagster daemon
defs = Definitions(
    assets=all_assets,
    jobs=[pipeline_execution_job],
    schedules=[realtime_api_poll_schedule]
)
