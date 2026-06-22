from fastapi import APIRouter, HTTPException
from ..schemas import ModelVersionInfo
from ...utils import get_mlflow_config

router = APIRouter(tags=["models"])


@router.get("", response_model=list[ModelVersionInfo])
def list_registered_models() -> list[ModelVersionInfo]:
    """Return all registered model names and their latest versions."""
    mlflow_cfg = get_mlflow_config()
    if mlflow_cfg is None:
        raise HTTPException(status_code=503, detail="MLflow disabled in config")
    try:
        import mlflow
        from mlflow.tracking import MlflowClient

        mlflow.set_tracking_uri(mlflow_cfg["tracking_uri"])
        client = MlflowClient()
        result = []
        for rm in client.search_registered_models():
            for v in client.get_latest_versions(rm.name):
                result.append(ModelVersionInfo(
                    name=rm.name,
                    version=v.version,
                    stage=v.current_stage,
                    run_id=v.run_id,
                    created_at=str(v.creation_timestamp),
                ))
        return result
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"MLflow unreachable: {exc}")
