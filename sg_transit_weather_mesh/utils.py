# sg_transit_weather_mesh/utils.py
import yaml
import os
import requests
import mlflow
from mlflow.entities import SpanType

_LM_URL   = "http://localhost:1234/api/v1/chat"
_LM_MODEL = "google/gemma-4-e4b"


def load_config():
    """Dynamically locates the root config folder and loads config.yaml."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "config.yaml")

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Missing configuration mapping layer target: {config_path}")

    with open(config_path, "r") as file:
        return yaml.safe_load(file)


def get_mlflow_config() -> dict | None:
    """Return the mlflow config section, or None when mlflow.enabled is false."""
    cfg = load_config()
    mlflow_cfg = cfg.get("mlflow", {})
    if not mlflow_cfg.get("enabled", False):
        return None
    return mlflow_cfg


def configure_mlflow_tracking(mlflow_cfg: dict) -> None:
    """Set MLflow tracking URI. MLFLOW_TRACKING_URI env var takes precedence over config."""
    uri = os.environ.get("MLFLOW_TRACKING_URI") or mlflow_cfg["tracking_uri"]
    mlflow.set_tracking_uri(uri)


@mlflow.trace(span_type=SpanType.LLM, name="lmstudio_completion")
def ask_llm(system_prompt: str, user_input: str, timeout: int = 8) -> str:
    """Call LMStudio local inference server. Returns response text, or empty string on failure."""
    try:
        resp = requests.post(
            _LM_URL,
            json={"model": _LM_MODEL, "system_prompt": system_prompt, "input": user_input},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if "choices" in data:
            return data["choices"][0]["message"]["content"].strip()
        return data.get("response", "").strip()
    except Exception:
        return ""
