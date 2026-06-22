"""FastAPI layer smoke tests — run without a live MLflow server."""
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from sg_transit_weather_mesh.api.main import create_app
from sg_transit_weather_mesh.api.model_store import ModelStore


def _make_client_no_mlflow():
    """Build a TestClient with MLflow disabled (get_mlflow_config returns None)."""
    with patch("sg_transit_weather_mesh.api.routes.health.get_mlflow_config", return_value=None), \
         patch("sg_transit_weather_mesh.utils.get_mlflow_config", return_value=None):
        app = create_app()
        return TestClient(app)


def _make_client_mlflow_disabled():
    """Build a TestClient whose model_store is empty (MLflow not reachable at startup)."""
    app = create_app()
    with patch("sg_transit_weather_mesh.utils.get_mlflow_config", return_value=None):
        return TestClient(app)


class TestHealth:
    def test_health_returns_200_always(self):
        with patch("sg_transit_weather_mesh.utils.load_config", return_value={
            "api": {"key": "k", "base_url": "u"},
            "orchestration": {"poll_cron_schedule": "*/5 * * * *"},
            "mlflow": {"enabled": False},
        }):
            app = create_app()
            client = TestClient(app)
            resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_schema(self):
        with patch("sg_transit_weather_mesh.utils.load_config", return_value={
            "api": {"key": "k", "base_url": "u"},
            "orchestration": {"poll_cron_schedule": "*/5 * * * *"},
            "mlflow": {"enabled": False},
        }):
            app = create_app()
            client = TestClient(app)
            data = client.get("/health").json()
        assert "status" in data
        assert "mlflow_available" in data
        assert "models_loaded" in data
        assert data["status"] in ("ok", "degraded")

    def test_health_degraded_without_model(self):
        with patch("sg_transit_weather_mesh.utils.load_config", return_value={
            "api": {"key": "k", "base_url": "u"},
            "orchestration": {"poll_cron_schedule": "*/5 * * * *"},
            "mlflow": {"enabled": False},
        }):
            app = create_app()
            client = TestClient(app)
            data = client.get("/health").json()
        assert data["status"] == "degraded"
        assert data["models_loaded"] is False


class TestPredictDemand:
    def test_predict_503_when_no_model(self):
        with patch("sg_transit_weather_mesh.utils.load_config", return_value={
            "api": {"key": "k", "base_url": "u"},
            "orchestration": {"poll_cron_schedule": "*/5 * * * *"},
            "mlflow": {"enabled": False},
        }):
            app = create_app()
            client = TestClient(app)
            resp = client.post("/predict/demand", json={
                "zones": [{
                    "zone_id": "h1",
                    "zone_name": "Marina Bay / CBD",
                    "lag_counts": [10, 12, 11, 9, 8, 10],
                }]
            })
        assert resp.status_code == 503

    def test_predict_returns_predictions_when_model_loaded(self):
        """Inject a mock model into model_store and verify prediction shape."""
        import numpy as np
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([42.7])

        with patch("sg_transit_weather_mesh.utils.load_config", return_value={
            "api": {"key": "k", "base_url": "u"},
            "orchestration": {"poll_cron_schedule": "*/5 * * * *"},
            "mlflow": {"enabled": False},
        }):
            app = create_app()
            # Directly inject a ready model_store
            from sg_transit_weather_mesh.api import model_store as ms_module
            ms_module.model_store.demand_models = {"latest": mock_model, "_version": "1"}
            ms_module.model_store.mlflow_available = True
            try:
                client = TestClient(app)
                resp = client.post("/predict/demand", json={
                    "zones": [{
                        "zone_id": "h1",
                        "zone_name": "Marina Bay / CBD",
                        "lag_counts": [10, 12, 11, 9, 8, 10],
                    }]
                })
                assert resp.status_code == 200
                data = resp.json()
                assert "predictions" in data
                assert data["predictions"][0]["zone_id"] == "h1"
                assert data["predictions"][0]["predicted_count"] == 43
            finally:
                ms_module.model_store.demand_models = None
                ms_module.model_store.mlflow_available = False


class TestExperiments:
    def test_unknown_experiment_name_404(self):
        with patch("sg_transit_weather_mesh.utils.load_config", return_value={
            "api": {"key": "k", "base_url": "u"},
            "orchestration": {"poll_cron_schedule": "*/5 * * * *"},
            "mlflow": {"enabled": False},
        }):
            app = create_app()
            client = TestClient(app)
            resp = client.get("/experiments/nonexistent/runs")
        assert resp.status_code == 404

    def test_known_experiment_503_when_mlflow_disabled(self):
        with patch("sg_transit_weather_mesh.utils.load_config", return_value={
            "api": {"key": "k", "base_url": "u"},
            "orchestration": {"poll_cron_schedule": "*/5 * * * *"},
            "mlflow": {"enabled": False},
        }):
            app = create_app()
            client = TestClient(app)
            resp = client.get("/experiments/demand_forecast/runs")
        assert resp.status_code == 503


class TestModels:
    def test_models_503_when_mlflow_disabled(self):
        with patch("sg_transit_weather_mesh.utils.load_config", return_value={
            "api": {"key": "k", "base_url": "u"},
            "orchestration": {"poll_cron_schedule": "*/5 * * * *"},
            "mlflow": {"enabled": False},
        }):
            app = create_app()
            client = TestClient(app)
            resp = client.get("/models")
        assert resp.status_code == 503
