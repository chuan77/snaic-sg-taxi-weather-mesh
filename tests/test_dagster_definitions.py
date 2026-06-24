"""Tests for Dagster job and schedule definitions (FR-2)."""
from dagster import JobDefinition, ScheduleDefinition

from sg_transit_weather_mesh import defs


def _job(name: str) -> JobDefinition:
    job = defs.get_job_def(name)
    assert job is not None, f"Job '{name}' not registered in Definitions"
    return job


def _schedule(name: str) -> ScheduleDefinition:
    schedule = defs.get_schedule_def(name)
    assert schedule is not None, f"Schedule '{name}' not registered in Definitions"
    return schedule


def _job_asset_keys(job: JobDefinition) -> set[str]:
    return {node_def.name for node_def in job.graph.node_defs}


class TestSyncJob:
    def test_sync_job_exists(self):
        _job("sg_taxi_weather_sync_job")

    def test_sync_job_excludes_demand_forecast(self):
        job = _job("sg_taxi_weather_sync_job")
        keys = _job_asset_keys(job)
        assert "demand_forecast_export" not in keys, (
            "demand_forecast_export must not be in the 5-min sync job"
        )

    def test_sync_job_includes_core_assets(self):
        job = _job("sg_taxi_weather_sync_job")
        keys = _job_asset_keys(job)
        for expected in ["ingest_sg_raw_data", "hotspots_export", "taxis_export"]:
            assert expected in keys, f"Expected '{expected}' in sync job"

    def test_sync_schedule_cron(self):
        schedule = _schedule("data_gov_sg_realtime_poll_schedule")
        assert schedule.cron_schedule == "*/5 * * * *"

    def test_sync_schedule_timezone(self):
        schedule = _schedule("data_gov_sg_realtime_poll_schedule")
        assert schedule.execution_timezone == "Asia/Singapore"


class TestDemandForecastJob:
    def test_forecast_job_exists(self):
        _job("demand_forecast_job")

    def test_forecast_job_includes_demand_forecast(self):
        job = _job("demand_forecast_job")
        keys = _job_asset_keys(job)
        assert "demand_forecast_export" in keys

    def test_forecast_schedule_exists(self):
        _schedule("demand_forecast_retrain_schedule")

    def test_forecast_schedule_cron(self):
        from sg_transit_weather_mesh.utils import load_config
        config = load_config()
        expected = config["orchestration"].get("forecast_retrain_cron_schedule", "0 * * * *")
        schedule = _schedule("demand_forecast_retrain_schedule")
        assert schedule.cron_schedule == expected

    def test_forecast_schedule_timezone(self):
        schedule = _schedule("demand_forecast_retrain_schedule")
        assert schedule.execution_timezone == "Asia/Singapore"
