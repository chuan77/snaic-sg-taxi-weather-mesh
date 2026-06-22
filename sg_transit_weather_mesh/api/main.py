"""
FastAPI application for the SG Transit Weather Mesh ML serving layer.

Start with:
    uv run uvicorn sg_transit_weather_mesh.api.main:app --port 8000 --reload

Swagger docs at: http://localhost:8000/docs
"""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..utils import get_mlflow_config
from .model_store import model_store
from .routes import health, models, predict, experiments

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    mlflow_cfg = get_mlflow_config()
    if mlflow_cfg is not None:
        model_store.load(mlflow_cfg)
    else:
        logger.info("MLflow disabled in config — model_store left empty")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="SG Transit Weather Mesh — ML API",
        version="0.1.0",
        description=(
            "On-demand inference and experiment history for the SG taxi demand pipeline. "
            "Start the MLflow tracking server first (port 5000), then run the Dagster pipeline "
            "to register a model before using the /predict endpoints."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://localhost:3000",
            "http://frontend:5173",
            *([o] if (o := os.environ.get("CORS_ORIGIN")) else []),
        ],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(models.router, prefix="/models")
    app.include_router(predict.router, prefix="/predict")
    app.include_router(experiments.router, prefix="/experiments")

    return app


app = create_app()
