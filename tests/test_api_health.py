"""FastAPI layer smoke tests — run without a live MLflow server."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from sg_transit_weather_mesh.api.main import create_app



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


def test_predict_demand_endpoint_removed():
    from fastapi.testclient import TestClient
    from unittest.mock import patch
    from sg_transit_weather_mesh.api.main import create_app
    with patch("sg_transit_weather_mesh.utils.load_config", return_value={
        "api": {"key": "k", "base_url": "u"},
        "orchestration": {"poll_cron_schedule": "*/5 * * * *"},
        "mlflow": {"enabled": False},
    }):
        app = create_app()
        client = TestClient(app)
        resp = client.post("/predict/demand", json={"zones": []})
    assert resp.status_code == 404


