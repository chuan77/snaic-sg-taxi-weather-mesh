from fastapi import APIRouter
from ..schemas import HealthResponse
from ..model_store import model_store
from ...utils import get_mlflow_config

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    mlflow_cfg = get_mlflow_config()
    return HealthResponse(
        status="ok" if model_store.ready else "degraded",
        mlflow_available=model_store.mlflow_available,
        models_loaded=model_store.ready,
        tracking_uri=mlflow_cfg["tracking_uri"] if mlflow_cfg else None,
    )
