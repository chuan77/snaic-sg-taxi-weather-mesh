# Availability Pattern Champion Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a champion selection process to `availability_pattern_export` that promotes the best-performing Ridge model to the `@champion` alias in the MLflow Model Registry, guarded by a `train_val_mae_gap` overfitting threshold.

**Architecture:** After each training run, a helper resolves the current `@champion` alias (if any) and fetches its `val_mae` from its MLflow run. The new model is promoted only when it passes the guardrail (`train_val_mae_gap ≤ 20`) and achieves a strictly lower `val_mae`. All branching outcomes are recorded as MLflow run tags for auditability.

**Tech Stack:** Python, MLflow (`MlflowClient`, `set_registered_model_alias`, `set_tag`), scikit-learn Ridge pipeline (unchanged).

## Global Constraints

- All changes confined to `sg_transit_weather_mesh/assets/analytics.py` and `tests/test_analytics.py`.
- `MlflowClient` is already available via the `mlflow` import — no new dependency.
- Champion threshold constant: `_CHAMPION_GAP_THRESHOLD = 20` (taxis, absolute).
- MLflow alias name: `"champion"` (string literal, no `@` prefix in the API call).
- Registered model name resolved from `_mlflow_cfg["registry"]["availability_pattern"]` — do not hardcode.
- Do not modify `pattern.json` schema, `chat_context_export`, `ModelStore`, or any other asset.
- All existing tests must continue to pass.

---

### Task 1: Add `_CHAMPION_GAP_THRESHOLD` constant and `_get_champion_val_mae` helper

**Files:**
- Modify: `sg_transit_weather_mesh/assets/analytics.py` — add constant near top of file (after existing `_PROJECT_ROOT` / path constants), add inline helper inside the `availability_pattern_export` function's MLflow block.
- Test: `tests/test_analytics.py`

**Interfaces:**
- Produces: `_CHAMPION_GAP_THRESHOLD: int = 20` (module-level constant)
- Produces: `_get_champion_val_mae(client: mlflow.MlflowClient, model_name: str) -> float | None`
  - Returns the `val_mae` metric (float) of the run currently aliased as `"champion"` on `model_name`.
  - Returns `None` if no `"champion"` alias exists or if the metric cannot be fetched.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_analytics.py`:

```python
from unittest.mock import MagicMock, patch


def _make_mock_client(champion_run_id=None, val_mae=None):
    """Build a MlflowClient mock for _get_champion_val_mae tests."""
    client = MagicMock()
    if champion_run_id is None:
        # No alias exists
        from mlflow.exceptions import MlflowException
        client.get_model_version_by_alias.side_effect = MlflowException("no alias")
    else:
        mv = MagicMock()
        mv.run_id = champion_run_id
        client.get_model_version_by_alias.return_value = mv
        metric = MagicMock()
        metric.value = val_mae
        client.get_metric_history.return_value = [metric] if val_mae is not None else []
    return client


def test_get_champion_val_mae_no_alias():
    """Returns None when no @champion alias exists."""
    from sg_transit_weather_mesh.assets.analytics import _get_champion_val_mae
    client = _make_mock_client(champion_run_id=None)
    result = _get_champion_val_mae(client, "TaxiAvailabilityPattern")
    assert result is None


def test_get_champion_val_mae_with_alias():
    """Returns val_mae float when @champion alias exists."""
    from sg_transit_weather_mesh.assets.analytics import _get_champion_val_mae
    client = _make_mock_client(champion_run_id="run-abc", val_mae=12.5)
    result = _get_champion_val_mae(client, "TaxiAvailabilityPattern")
    assert result == 12.5


def test_get_champion_val_mae_empty_metric_history():
    """Returns None when metric history is empty (metric not logged)."""
    from sg_transit_weather_mesh.assets.analytics import _get_champion_val_mae
    client = _make_mock_client(champion_run_id="run-abc", val_mae=None)
    result = _get_champion_val_mae(client, "TaxiAvailabilityPattern")
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_analytics.py::test_get_champion_val_mae_no_alias tests/test_analytics.py::test_get_champion_val_mae_with_alias tests/test_analytics.py::test_get_champion_val_mae_empty_metric_history -v
```

Expected: `ImportError` or `AttributeError` — `_get_champion_val_mae` does not exist yet.

- [ ] **Step 3: Add the constant and helper to `analytics.py`**

Near the top of `analytics.py`, after the existing path constants (search for `_PROJECT_ROOT`), add:

```python
_CHAMPION_GAP_THRESHOLD = 20  # taxis; guardrail for train_val_mae_gap before champion promotion
```

Inside `availability_pattern_export`, add this helper function definition just before the `# MLflow logging` comment (around line 1492):

```python
def _get_champion_val_mae(client, model_name: str):
    try:
        mv = client.get_model_version_by_alias(model_name, "champion")
        history = client.get_metric_history(mv.run_id, "val_mae")
        return history[0].value if history else None
    except Exception:
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_analytics.py::test_get_champion_val_mae_no_alias tests/test_analytics.py::test_get_champion_val_mae_with_alias tests/test_analytics.py::test_get_champion_val_mae_empty_metric_history -v
```

Expected: all 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add sg_transit_weather_mesh/assets/analytics.py tests/test_analytics.py
git commit -m "feat: add _CHAMPION_GAP_THRESHOLD constant and _get_champion_val_mae helper"
```

---

### Task 2: Wire champion selection into the MLflow block

**Files:**
- Modify: `sg_transit_weather_mesh/assets/analytics.py` — replace the `mlflow.sklearn.log_model(...)` call and its surrounding `with mlflow.start_run` block with the extended version that performs champion selection.
- Test: `tests/test_analytics.py`

**Interfaces:**
- Consumes: `_CHAMPION_GAP_THRESHOLD: int` (module-level constant from Task 1)
- Consumes: `_get_champion_val_mae(client, model_name) -> float | None` (from Task 1)
- The existing `_mlflow_cfg["registry"]["availability_pattern"]` string is the `model_name` throughout.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_analytics.py`:

```python
def _make_log_model_result(version="3"):
    """Simulate the ModelVersion object returned by mlflow.sklearn.log_model."""
    mv = MagicMock()
    mv.registered_model_name = "TaxiAvailabilityPattern"
    mv.version = version
    return mv


def test_champion_guardrail_skips_promotion():
    """gap > threshold → no alias set, tag champion_skipped=guardrail_failed."""
    from sg_transit_weather_mesh.assets.analytics import (
        _CHAMPION_GAP_THRESHOLD,
        _get_champion_val_mae,
    )
    client = MagicMock()
    # Simulate: gap exceeds threshold
    gap = _CHAMPION_GAP_THRESHOLD + 1  # 21
    val_mae = 10.0
    model_name = "TaxiAvailabilityPattern"
    version = "3"

    promote, tags = _champion_selection_result(client, model_name, version, val_mae, gap)

    assert promote is False
    assert tags.get("champion_skipped") == "guardrail_failed"
    client.set_registered_model_alias.assert_not_called()


def test_champion_first_run_promotes():
    """No existing champion + gap ≤ threshold → alias assigned."""
    from sg_transit_weather_mesh.assets.analytics import _CHAMPION_GAP_THRESHOLD
    client = _make_mock_client(champion_run_id=None)
    gap = _CHAMPION_GAP_THRESHOLD - 1  # 19
    val_mae = 10.0
    model_name = "TaxiAvailabilityPattern"
    version = "3"

    promote, tags = _champion_selection_result(client, model_name, version, val_mae, gap)

    assert promote is True
    assert tags.get("champion_promoted") == "true"
    client.set_registered_model_alias.assert_called_once_with(model_name, "champion", version)


def test_champion_better_model_promotes():
    """New val_mae < current champion val_mae + gap ≤ threshold → alias reassigned."""
    client = _make_mock_client(champion_run_id="run-old", val_mae=15.0)
    gap = 5.0
    val_mae = 12.0  # better
    model_name = "TaxiAvailabilityPattern"
    version = "4"

    promote, tags = _champion_selection_result(client, model_name, version, val_mae, gap)

    assert promote is True
    assert tags.get("champion_promoted") == "true"
    assert tags.get("champion_val_mae") == "15.0"
    client.set_registered_model_alias.assert_called_once_with(model_name, "champion", version)


def test_champion_worse_model_no_promotion():
    """New val_mae ≥ current champion val_mae → no alias change."""
    client = _make_mock_client(champion_run_id="run-old", val_mae=10.0)
    gap = 5.0
    val_mae = 12.0  # worse
    model_name = "TaxiAvailabilityPattern"
    version = "4"

    promote, tags = _champion_selection_result(client, model_name, version, val_mae, gap)

    assert promote is False
    assert tags.get("champion_promoted") == "false"
    assert tags.get("champion_val_mae") == "10.0"
    client.set_registered_model_alias.assert_not_called()
```

Note: these tests call `_champion_selection_result` — a small pure function you will extract in Step 3 to make the logic unit-testable without mocking the full MLflow run context.

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_analytics.py::test_champion_guardrail_skips_promotion tests/test_analytics.py::test_champion_first_run_promotes tests/test_analytics.py::test_champion_better_model_promotes tests/test_analytics.py::test_champion_worse_model_no_promotion -v
```

Expected: `ImportError` — `_champion_selection_result` does not exist yet.

- [ ] **Step 3: Add `_champion_selection_result` and wire it into the MLflow block**

**3a.** Add the following pure function to `analytics.py`, directly after `_get_champion_val_mae` (still inside `availability_pattern_export`, before the `# MLflow logging` comment):

```python
def _champion_selection_result(client, model_name: str, version: str, val_mae: float, gap: float):
    """Evaluate whether the new model version should become champion.

    Returns (promoted: bool, tags: dict[str, str]).
    Side-effect: calls client.set_registered_model_alias when promoted=True.
    """
    tags = {}
    if gap > _CHAMPION_GAP_THRESHOLD:
        tags["champion_skipped"] = "guardrail_failed"
        return False, tags

    current_val_mae = _get_champion_val_mae(client, model_name)
    if current_val_mae is not None:
        tags["champion_val_mae"] = str(current_val_mae)

    if current_val_mae is None or val_mae < current_val_mae:
        client.set_registered_model_alias(model_name, "champion", version)
        tags["champion_promoted"] = "true"
        return True, tags

    tags["champion_promoted"] = "false"
    return False, tags
```

**3b.** Replace the existing MLflow block (lines ~1492–1516) with:

```python
    # MLflow logging
    _mlflow_cfg = get_mlflow_config()
    if _mlflow_cfg is not None:
        try:
            configure_mlflow_tracking(_mlflow_cfg)
            mlflow.set_experiment(_mlflow_cfg["experiments"]["availability_pattern"])
            with mlflow.start_run(run_name=f"ridge_{datetime.now().strftime('%Y%m%dT%H%M')}") as active_run:
                mlflow.log_params({"alpha": 1.0, "train_split": 0.8})
                mlflow.log_metric("train_mae", train_mae)
                mlflow.log_metric("val_mae", val_mae)
                mlflow.log_metric("val_rmse", val_rmse)
                mlflow.log_metric("val_r2", val_r2)
                mlflow.log_metric("train_val_mae_gap", train_val_mae_gap)
                mlflow.log_metric("n_training_rows", len(train_rows))
                mlflow.log_metric("n_planning_areas", len(all_areas))
                for pa, mae_val in area_val_mae.items():
                    key = "area_mae_" + pa.lower().replace(" ", "_")
                    mlflow.log_metric(key, mae_val)
                model_info = mlflow.sklearn.log_model(
                    sk_model=pipeline,
                    artifact_path="model",
                    registered_model_name=_mlflow_cfg["registry"]["availability_pattern"],
                )
                # Champion selection
                _client = mlflow.MlflowClient()
                _model_name = _mlflow_cfg["registry"]["availability_pattern"]
                _version = model_info.registered_model_version
                _, _tags = _champion_selection_result(
                    _client, _model_name, _version, val_mae, train_val_mae_gap
                )
                for _tag_key, _tag_val in _tags.items():
                    mlflow.set_tag(_tag_key, _tag_val)
        except Exception as exc:
            _log.warning(f"MLflow logging for availability_pattern_export failed: {exc}")
```

- [ ] **Step 4: Run the new champion selection tests**

```bash
uv run pytest tests/test_analytics.py::test_champion_guardrail_skips_promotion tests/test_analytics.py::test_champion_first_run_promotes tests/test_analytics.py::test_champion_better_model_promotes tests/test_analytics.py::test_champion_worse_model_no_promotion -v
```

Expected: all 4 PASS.

- [ ] **Step 5: Run the full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all existing tests continue to pass alongside the 7 new tests.

- [ ] **Step 6: Commit**

```bash
git add sg_transit_weather_mesh/assets/analytics.py tests/test_analytics.py
git commit -m "feat: champion selection for TaxiAvailabilityPattern via @champion MLflow alias"
```
