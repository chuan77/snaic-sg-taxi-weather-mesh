from __future__ import annotations
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    mlflow_available: bool
    models_loaded: bool
    tracking_uri: str | None


class ZoneForecastItem(BaseModel):
    zone_id: str = Field(examples=["h1"])
    zone_name: str = Field(examples=["Marina Bay / CBD"])
    lag_counts: list[int] = Field(
        min_length=6,
        max_length=6,
        description="Last 6 taxi counts (most-recent first). Length must equal LAG=6.",
    )


class DemandPredictRequest(BaseModel):
    zones: list[ZoneForecastItem]


class ZonePrediction(BaseModel):
    zone_id: str
    predicted_count: int
    model_version: str | None


class DemandPredictResponse(BaseModel):
    predictions: list[ZonePrediction]
    horizon_minutes: int = 30


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
