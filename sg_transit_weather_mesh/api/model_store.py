"""
ModelStore: loads registered models from MLflow at FastAPI startup.
Thread-safe after init — models are read-only after load.
"""
from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ModelStore:
    """Holds references to models loaded from the MLflow registry.

    Attributes are None when MLflow is unavailable or the registry is empty.
    FastAPI health route reads model_store.mlflow_available and model_store.ready.
    """

    def __init__(self) -> None:
        self.demand_models: dict[str, Any] | None = None
        self.mlflow_available: bool = False
        self._tracking_uri: str | None = None

    def load(self, mlflow_cfg: dict) -> None:
        """Attempt to load models from MLflow registry. Never raises."""
        try:
            import mlflow
            import mlflow.sklearn
            from mlflow.tracking import MlflowClient

            mlflow.set_tracking_uri(mlflow_cfg["tracking_uri"])
            self._tracking_uri = mlflow_cfg["tracking_uri"]
            client = MlflowClient()

            model_name = mlflow_cfg["registry"]["demand_forecast"]
            versions = client.get_latest_versions(model_name, stages=["Production"])
            if not versions:
                versions = client.get_latest_versions(model_name)
            if not versions:
                logger.warning("No registered versions found for %s", model_name)
                self.mlflow_available = True
                return

            latest = versions[0]
            model_uri = f"models:/{model_name}/{latest.version}"
            loaded = mlflow.sklearn.load_model(model_uri)

            self.demand_models = {"latest": loaded, "_version": latest.version}
            self.mlflow_available = True
            logger.info("Loaded %s version %s from MLflow", model_name, latest.version)

        except Exception as exc:
            logger.warning("MLflow model load failed (non-fatal): %s", exc)

    @property
    def ready(self) -> bool:
        return self.mlflow_available and self.demand_models is not None


model_store = ModelStore()
