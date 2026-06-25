"""
FastAPI application for the SG Transit Weather Mesh ML serving layer.

Start with:
    uv run uvicorn sg_transit_weather_mesh.api.main:app --port 8000 --reload

Swagger docs at: http://localhost:8000/docs
"""
from __future__ import annotations
import logging

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import health, experiments

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="SG Transit Weather Mesh — ML API",
        version="0.1.0",
        description=(
            "Experiment history for the SG taxi demand pipeline. "
            "Start the MLflow tracking server first (port 5050), then run the Dagster pipeline "
            "to register models."
        ),
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
    app.include_router(experiments.router, prefix="/experiments")

    return app


app = create_app()
