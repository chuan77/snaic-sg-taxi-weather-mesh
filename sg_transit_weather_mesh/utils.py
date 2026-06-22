# sg_transit_weather_mesh/utils.py
import yaml
import os
import requests
import mlflow
from mlflow.entities import SpanType

# Docker Model Runner endpoint (from containers: model-runner.docker.internal; from host: localhost:12434)
# Override via LLM_BASE_URL env var for local dev with LMStudio or other providers.
_LM_BASE  = os.environ.get("LLM_BASE_URL", "http://localhost:12434/engines/v1")
_LM_MODEL = os.environ.get("LLM_MODEL", "ai/gemma4:E4B")


def load_config():
    """Dynamically locates the root config folder and loads config.yaml."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "config.yaml")

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Missing configuration mapping layer target: {config_path}")

    with open(config_path, "r") as file:
        cfg = yaml.safe_load(file)

    # Allow DATA_GOV_API_KEY env var to override the key in config.yaml (used in Docker)
    env_key = os.environ.get("DATA_GOV_API_KEY")
    if env_key:
        cfg.setdefault("api", {})["key"] = env_key

    return cfg


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


@mlflow.trace(span_type=SpanType.LLM, name="dmr_completion")
def ask_llm(system_prompt: str, user_input: str, timeout: int = 8) -> str:
    """Call Docker Model Runner (OpenAI-compatible) inference endpoint. Returns response text, or empty string on failure."""
    try:
        resp = requests.post(
            f"{_LM_BASE}/chat/completions",
            json={
                "model": _LM_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_input},
                ],
                "temperature": 0.7,
                "max_tokens": 256,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return ""
