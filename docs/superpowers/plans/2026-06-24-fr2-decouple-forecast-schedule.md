# FR-2: Decouple Demand Forecast Retraining Schedule — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `demand_forecast_export` out of the 5-minute polling job into its own hourly Dagster job and schedule, so GBR retraining and MLflow registry writes happen once per hour instead of every 5 minutes.

**Architecture:** Two separate Dagster jobs share the same asset graph. The existing `sg_taxi_weather_sync_job` continues to run all ingestion and export assets every 5 minutes, minus `demand_forecast_export`. A new `demand_forecast_job` runs only `demand_forecast_export` on an independent cron (default: hourly). Because `demand_forecast_export` reads from `warehouse.duckdb` directly (not via Dagster I/O manager), it works correctly as a standalone job against already-populated data.

**Tech Stack:** Dagster (`define_asset_job`, `ScheduleDefinition`, `Definitions`), PyYAML config, pytest

## Global Constraints

- Execution timezone for all schedules: `Asia/Singapore`
- Config is loaded from `config/config.yaml` via `load_config()` in `utils.py`
- All Dagster objects must be registered in the `Definitions` export in `sg_transit_weather_mesh/__init__.py`
- No changes to `analytics.py` — the asset definition is untouched

---

## File Map

| File | Change |
|------|--------|
| `config/config.yaml` | Add `forecast_retrain_cron_schedule` key under `orchestration` |
| `sg_transit_weather_mesh/__init__.py` | Remove `demand_forecast_export` from main job; add new job + schedule |
| `tests/test_dagster_definitions.py` | New test file verifying job selections and schedule crons |

---

### Task 1: Add config key + write the failing test

**Files:**
- Modify: `config/config.yaml`
- Create: `tests/test_dagster_definitions.py`

**Interfaces:**
- Produces: `load_config()["orchestration"]["forecast_retrain_cron_schedule"]` → `str` (hourly cron string)

- [ ] **Step 1: Add the new config key to config.yaml**

Open `config/config.yaml` and add `forecast_retrain_cron_schedule` under `orchestration`:

```yaml
orchestration:
  poll_cron_schedule: "*/5 * * * *"
  forecast_retrain_cron_schedule: "0 * * * *"
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_dagster_definitions.py`:

```python
"""Tests for Dagster job and schedule definitions (FR-2)."""
import pytest
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
        schedule = _schedule("demand_forecast_retrain_schedule")
        assert schedule.cron_schedule == "0 * * * *"

    def test_forecast_schedule_timezone(self):
        schedule = _schedule("demand_forecast_retrain_schedule")
        assert schedule.execution_timezone == "Asia/Singapore"
```

- [ ] **Step 3: Run to verify tests fail**

```bash
uv run pytest tests/test_dagster_definitions.py -v
```

Expected: FAIL — `demand_forecast_job` and `demand_forecast_retrain_schedule` don't exist yet; `demand_forecast_export` is still in the sync job.

---

### Task 2: Update `__init__.py` to split the jobs

**Files:**
- Modify: `sg_transit_weather_mesh/__init__.py`

**Interfaces:**
- Consumes: `load_config()["orchestration"]["forecast_retrain_cron_schedule"]` (from Task 1)
- Produces: `defs` with two jobs (`sg_taxi_weather_sync_job`, `demand_forecast_job`) and two schedules

- [ ] **Step 1: Replace `__init__.py` with the two-job definition**

Replace the entire contents of `sg_transit_weather_mesh/__init__.py`:

```python
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
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest tests/test_dagster_definitions.py -v
```

Expected: All 10 tests PASS.

- [ ] **Step 3: Run the full test suite to check for regressions**

```bash
uv run pytest tests -v
```

Expected: All existing tests pass. Pay attention to any test that imports from `sg_transit_weather_mesh` or mocks `load_config`.

- [ ] **Step 4: Commit**

```bash
git add config/config.yaml sg_transit_weather_mesh/__init__.py tests/test_dagster_definitions.py
git commit -m "feat: decouple demand_forecast_export into separate hourly Dagster job (FR-2)"
```

---

## Verification

1. **Unit tests:** `uv run pytest tests/test_dagster_definitions.py -v` — all 10 pass
2. **Regression:** `uv run pytest tests -v` — no existing tests broken
3. **Dagster UI (manual):** `uv run dagster dev` → open http://localhost:3000 → confirm two jobs visible: `sg_taxi_weather_sync_job` and `demand_forecast_job`; confirm two schedules with correct crons
4. **Dry run (manual):** In Dagster UI, trigger `demand_forecast_job` manually once — verify `forecast.json` is written and MLflow logs one run under `sg-taxi-demand-forecast`
