from __future__ import annotations
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    mlflow_available: bool
    models_loaded: bool
    tracking_uri: str | None


class ModelVersionInfo(BaseModel):
    name: str
    version: str
    stage: str
    run_id: str | None
    created_at: str | None


class ExperimentRunItem(BaseModel):
    run_id: str
    start_time: str
    status: str
    metrics: dict[str, float]
    params: dict[str, str]
    tags: dict[str, str]
