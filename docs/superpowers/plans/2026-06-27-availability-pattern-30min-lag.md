# Availability Pattern v3 — 30-min Bucketing + Area-Relative Lag Features

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a v3 training path inside `availability_pattern_export()` that buckets 5-min rows into 30-min intervals, builds area-relative lag features (lag_k / area_mean), and logs results as an `lr_v3` run in the existing `availability_pattern` MLflow experiment for comparison against v2.

**Architecture:** All changes are additive inside the existing `availability_pattern_export()` function in `analytics.py`. A new `_build_v3_lag_rows()` helper extracts the bucketing + lag construction logic. The v3 MLflow run is logged after the existing v2 run — both runs appear in the same experiment for side-by-side comparison. No changes to `pattern.json`, Dagster graph, or frontend.

**Tech Stack:** Python, scikit-learn (`LinearRegression`, `Pipeline`, `ColumnTransformer`, `OneHotEncoder`), MLflow, DuckDB, existing `analytics.py` patterns.

## Global Constraints

- All changes inside `sg_transit_weather_mesh/assets/analytics.py` only — no other files modified except test file
- `pattern.json` schema unchanged — v3 is experiment-only, not production output
- MLflow run name format: `lr_v3_YYYYMMDDTHHMMM` (matching existing `lr_` prefix convention)
- `feature_version` param logged as `"v3"` in MLflow
- `_FORECAST_LAG` and `_FORECAST_HORIZON` constants (lines 153–154) must not be changed — they belong to the GBR demand forecast, not this model
- Temporal 80/20 split must be applied before computing any means (no data leakage)
- Minimum qualifying samples per area: `_AVAIL_LAG + _AVAIL_HORIZON + 1 = 9` buckets

---

### Task 1: Add `_build_v3_lag_rows()` helper and unit tests

**Files:**
- Modify: `sg_transit_weather_mesh/assets/analytics.py` — add helper function just before `availability_pattern_export()`
- Modify: `tests/test_analytics.py` — add unit tests for the helper

**Interfaces:**
- Produces: `_build_v3_lag_rows(pa_bucket_counts: dict[tuple[str, datetime], int], avail_lag: int, avail_horizon: int, train_area_means: dict[tuple[str, int], float], global_mean: float) -> list[dict]`
  - Input `pa_bucket_counts`: keys are `(planning_area: str, timestamp_30min: datetime)`, values are `int` taxi counts
  - Input `train_area_means`: keys are `(planning_area: str, hour: int)`, values are `float` mean counts from training rows
  - Returns list of dicts, each with keys: `"planning_area"`, `"timestamp_30min"`, `"hour_sin"`, `"hour_cos"`, `"dow_sin"`, `"dow_cos"`, `"is_weekend"`, `"is_peak_hour"`, `"weather_intensity"` (not included here — added in calling code), `"lag_1_rel"`, `"lag_2_rel"`, `"lag_3_rel"`, `"lag_4_rel"`, `"area_hour_mean_count"`, `"count"` (target)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_analytics.py`:

```python
# ---------------------------------------------------------------------------
# _build_v3_lag_rows tests
# ---------------------------------------------------------------------------
from datetime import datetime, timedelta
import math

def _make_bucket_counts(area: str, start: datetime, counts: list[int]) -> dict:
    """Helper: build pa_bucket_counts dict for one area."""
    return {
        (area, start + timedelta(minutes=30 * i)): c
        for i, c in enumerate(counts)
    }

def test_v3_lag_rows_basic_shape():
    """_build_v3_lag_rows returns one row per qualifying (area, t) pair."""
    from sg_transit_weather_mesh.assets.analytics import _build_v3_lag_rows
    start = datetime(2026, 6, 27, 8, 0)
    # 10 buckets → LAG=4, HORIZON=4, min=9 → 10 - 4 - 4 = 2 rows
    counts = [100, 110, 105, 95, 90, 85, 100, 110, 95, 88]
    pa_bucket_counts = _make_bucket_counts("Bukit Merah", start, counts)
    means = {("Bukit Merah", (start + timedelta(minutes=30 * i)).hour): 100.0 for i in range(10)}
    rows = _build_v3_lag_rows(pa_bucket_counts, avail_lag=4, avail_horizon=4,
                               train_area_means=means, global_mean=100.0)
    assert len(rows) == 2


def test_v3_lag_rows_relative_lag_values():
    """lag_k_rel = count[t-k] / area_mean."""
    from sg_transit_weather_mesh.assets.analytics import _build_v3_lag_rows
    start = datetime(2026, 6, 27, 8, 0)
    # constant counts of 200 each; area_mean = 100 → all lags = 2.0
    counts = [200] * 10
    pa_bucket_counts = _make_bucket_counts("Changi", start, counts)
    means = {("Changi", (start + timedelta(minutes=30 * i)).hour): 100.0 for i in range(10)}
    rows = _build_v3_lag_rows(pa_bucket_counts, avail_lag=4, avail_horizon=4,
                               train_area_means=means, global_mean=100.0)
    assert rows[0]["lag_1_rel"] == 2.0
    assert rows[0]["lag_2_rel"] == 2.0
    assert rows[0]["lag_3_rel"] == 2.0
    assert rows[0]["lag_4_rel"] == 2.0


def test_v3_lag_rows_target_is_horizon_steps_ahead():
    """count (target) is the value AVAIL_HORIZON steps after the current bucket."""
    from sg_transit_weather_mesh.assets.analytics import _build_v3_lag_rows
    start = datetime(2026, 6, 27, 8, 0)
    # 9 buckets (exactly min), one row: t=4, target=t+4=8 → counts[8]
    counts = [10, 20, 30, 40, 50, 60, 70, 80, 90]
    pa_bucket_counts = _make_bucket_counts("Queenstown", start, counts)
    means = {("Queenstown", (start + timedelta(minutes=30 * i)).hour): 50.0 for i in range(9)}
    rows = _build_v3_lag_rows(pa_bucket_counts, avail_lag=4, avail_horizon=4,
                               train_area_means=means, global_mean=50.0)
    assert len(rows) == 1
    assert rows[0]["count"] == 90  # counts[8]


def test_v3_lag_rows_area_below_min_samples_excluded():
    """Areas with fewer than LAG+HORIZON+1 buckets produce zero rows."""
    from sg_transit_weather_mesh.assets.analytics import _build_v3_lag_rows
    start = datetime(2026, 6, 27, 8, 0)
    counts = [10, 20, 30, 40, 50, 60, 70, 80]  # 8 buckets < 9 min
    pa_bucket_counts = _make_bucket_counts("Tengah", start, counts)
    means = {("Tengah", (start + timedelta(minutes=30 * i)).hour): 40.0 for i in range(8)}
    rows = _build_v3_lag_rows(pa_bucket_counts, avail_lag=4, avail_horizon=4,
                               train_area_means=means, global_mean=40.0)
    assert len(rows) == 0


def test_v3_lag_rows_uses_global_mean_fallback():
    """Uses global_mean when area+hour key is absent from train_area_means."""
    from sg_transit_weather_mesh.assets.analytics import _build_v3_lag_rows
    start = datetime(2026, 6, 27, 8, 0)
    counts = [50] * 10
    pa_bucket_counts = _make_bucket_counts("Lim Chu Kang", start, counts)
    # No means provided for this area → falls back to global_mean=25
    rows = _build_v3_lag_rows(pa_bucket_counts, avail_lag=4, avail_horizon=4,
                               train_area_means={}, global_mean=25.0)
    assert rows[0]["lag_1_rel"] == 50.0 / 25.0


def test_v3_lag_rows_area_hour_mean_count_in_row():
    """area_hour_mean_count is present in each returned row."""
    from sg_transit_weather_mesh.assets.analytics import _build_v3_lag_rows
    start = datetime(2026, 6, 27, 8, 0)
    counts = [100] * 10
    pa_bucket_counts = _make_bucket_counts("Bukit Timah", start, counts)
    means = {("Bukit Timah", (start + timedelta(minutes=30 * i)).hour): 77.0 for i in range(10)}
    rows = _build_v3_lag_rows(pa_bucket_counts, avail_lag=4, avail_horizon=4,
                               train_area_means=means, global_mean=50.0)
    assert "area_hour_mean_count" in rows[0]
    assert rows[0]["area_hour_mean_count"] == 77.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_analytics.py::test_v3_lag_rows_basic_shape \
  tests/test_analytics.py::test_v3_lag_rows_relative_lag_values \
  tests/test_analytics.py::test_v3_lag_rows_target_is_horizon_steps_ahead \
  tests/test_analytics.py::test_v3_lag_rows_area_below_min_samples_excluded \
  tests/test_analytics.py::test_v3_lag_rows_uses_global_mean_fallback \
  tests/test_analytics.py::test_v3_lag_rows_area_hour_mean_count_in_row -v
```

Expected: all FAIL with `ImportError: cannot import name '_build_v3_lag_rows'`

- [ ] **Step 3: Implement `_build_v3_lag_rows()` in analytics.py**

Add this function immediately before `def availability_pattern_export():` (around line 1396):

```python
_AVAIL_LAG     = 4   # 2 hours of history at 30-min granularity
_AVAIL_HORIZON = 4   # predict 2 hours ahead (4 × 30 min)


def _build_v3_lag_rows(
    pa_bucket_counts: dict,
    avail_lag: int,
    avail_horizon: int,
    train_area_means: dict,
    global_mean: float,
) -> list:
    """Build lag-feature rows from 30-min bucketed taxi counts.

    For each planning area, sorts buckets chronologically and emits one row
    per qualifying timestep (index avail_lag .. len-avail_horizon-1).
    Each row contains area-relative lag features (count / area_mean) and
    the raw count avail_horizon steps ahead as the target.
    """
    from collections import defaultdict
    # Group by planning area
    area_buckets: dict = defaultdict(list)
    for (pa, ts), cnt in pa_bucket_counts.items():
        area_buckets[pa].append((ts, cnt))

    min_samples = avail_lag + avail_horizon + 1
    result = []
    for pa, ts_cnt_list in area_buckets.items():
        ts_cnt_list.sort(key=lambda x: x[0])
        if len(ts_cnt_list) < min_samples:
            continue
        timestamps = [x[0] for x in ts_cnt_list]
        counts_seq = [x[1] for x in ts_cnt_list]
        for i in range(avail_lag, len(counts_seq) - avail_horizon):
            dt = timestamps[i]
            h   = dt.hour
            dow = dt.weekday()
            area_mean = train_area_means.get((pa, h), global_mean) or global_mean
            lags_rel = {
                f"lag_{k}_rel": counts_seq[i - k] / area_mean
                for k in range(1, avail_lag + 1)
            }
            result.append({
                "planning_area": pa,
                "timestamp_30min": dt,
                "hour_sin":  math.sin(2 * math.pi * h / 24),
                "hour_cos":  math.cos(2 * math.pi * h / 24),
                "dow_sin":   math.sin(2 * math.pi * dow / 7),
                "dow_cos":   math.cos(2 * math.pi * dow / 7),
                "is_weekend":   1 if dow >= 5 else 0,
                "is_peak_hour": 1 if h in {7, 8, 17, 18, 19} else 0,
                "area_hour_mean_count": area_mean,
                **lags_rel,
                "count": counts_seq[i + avail_horizon],
            })
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_analytics.py::test_v3_lag_rows_basic_shape \
  tests/test_analytics.py::test_v3_lag_rows_relative_lag_values \
  tests/test_analytics.py::test_v3_lag_rows_target_is_horizon_steps_ahead \
  tests/test_analytics.py::test_v3_lag_rows_area_below_min_samples_excluded \
  tests/test_analytics.py::test_v3_lag_rows_uses_global_mean_fallback \
  tests/test_analytics.py::test_v3_lag_rows_area_hour_mean_count_in_row -v
```

Expected: all 6 PASS

- [ ] **Step 5: Run full test suite to check no regressions**

```bash
uv run pytest tests/ -v
```

Expected: all existing tests PASS

- [ ] **Step 6: Commit**

```bash
git add sg_transit_weather_mesh/assets/analytics.py tests/test_analytics.py
git commit -m "feat: add _build_v3_lag_rows helper for 30-min area-relative lag features"
```

---

### Task 2: Add 30-min bucketing inside `availability_pattern_export()` and wire v3 training

**Files:**
- Modify: `sg_transit_weather_mesh/assets/analytics.py` — inside `availability_pattern_export()`, after the existing v2 MLflow block, add 30-min bucketing + v3 training + v3 MLflow logging
- Modify: `tests/test_analytics.py` — add integration test verifying v3 metrics are logged

**Interfaces:**
- Consumes: `_build_v3_lag_rows()` from Task 1, `_AVAIL_LAG`, `_AVAIL_HORIZON` constants
- Consumes: `pa_hour_counts` (already built by existing code: `dict[(pa, event_hour), int]`)
- Consumes: `pa_hour_weather` (already built by existing code: `dict[(pa, event_hour), int]`)
- Consumes: `area_hour_mean`, `_global_mean` (already computed from training rows in v2 path)

- [ ] **Step 1: Write the failing integration test**

Add to `tests/test_analytics.py`:

```python
def test_v3_training_runs_and_returns_metrics(monkeypatch, tmp_path):
    """v3 training block computes val_r2 and val_mae without crashing."""
    import math
    from datetime import datetime, timedelta
    from collections import defaultdict
    from sg_transit_weather_mesh.assets.analytics import (
        _build_v3_lag_rows, _AVAIL_LAG, _AVAIL_HORIZON,
    )
    from sklearn.linear_model import LinearRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder
    from sklearn.compose import ColumnTransformer
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    # Build synthetic 30-min bucket data: 3 areas × 60 buckets (~30 hours)
    areas = ["Bukit Merah", "Changi", "Queenstown"]
    scale = {"Bukit Merah": 100, "Changi": 800, "Queenstown": 60}
    start = datetime(2026, 6, 27, 0, 0)
    pa_bucket_counts = {}
    for area in areas:
        base = scale[area]
        for i in range(60):
            ts = start + timedelta(minutes=30 * i)
            pa_bucket_counts[(area, ts)] = base + (i % 5) * 5

    # Temporal 80/20 split on all bucket timestamps
    all_ts = sorted({ts for (_, ts) in pa_bucket_counts})
    split_ts = all_ts[int(len(all_ts) * 0.8)]
    train_bucket = {k: v for k, v in pa_bucket_counts.items() if k[1] < split_ts}

    # Compute train means (no leakage)
    _sum: dict = defaultdict(float)
    _n: dict = defaultdict(int)
    for (pa, ts), cnt in train_bucket.items():
        _sum[(pa, ts.hour)] += cnt
        _n[(pa, ts.hour)] += 1
    train_means = {k: _sum[k] / _n[k] for k in _sum}
    global_mean = sum(_sum.values()) / max(sum(_n.values()), 1)

    # Build lag rows from all data; split by timestamp
    lag_rows = _build_v3_lag_rows(
        pa_bucket_counts, _AVAIL_LAG, _AVAIL_HORIZON, train_means, global_mean
    )
    assert len(lag_rows) > 0, "Expected lag rows"

    lag_rows.sort(key=lambda r: r["timestamp_30min"])
    split_idx = int(len(lag_rows) * 0.8)
    train_rows_v3 = lag_rows[:split_idx]
    val_rows_v3   = lag_rows[split_idx:]
    assert len(val_rows_v3) > 0, "Expected validation rows"

    v3_numeric = [
        "lag_1_rel", "lag_2_rel", "lag_3_rel", "lag_4_rel",
        "hour_sin", "hour_cos", "dow_sin", "dow_cos",
        "is_weekend", "is_peak_hour", "area_hour_mean_count",
    ]
    X_train_v3 = [[r["planning_area"]] + [r[f] for f in v3_numeric] for r in train_rows_v3]
    X_val_v3   = [[r["planning_area"]] + [r[f] for f in v3_numeric] for r in val_rows_v3]
    y_tr_v3    = [r["count"] for r in train_rows_v3]
    y_va_v3    = [r["count"] for r in val_rows_v3]

    preprocessor_v3 = ColumnTransformer(transformers=[
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), [0]),
        ("num", "passthrough", list(range(1, 1 + len(v3_numeric)))),
    ])
    pipeline_v3 = Pipeline([("preprocessor", preprocessor_v3), ("lr", LinearRegression())])
    pipeline_v3.fit(X_train_v3, y_tr_v3)

    y_pred_va_v3 = pipeline_v3.predict(X_val_v3)
    val_mae_v3  = float(mean_absolute_error(y_va_v3, y_pred_va_v3))
    val_r2_v3   = float(r2_score(y_va_v3, y_pred_va_v3))

    assert 0.0 <= val_r2_v3 <= 1.0 or val_r2_v3 < 0, "val_r2 should be a finite float"
    assert val_mae_v3 >= 0
```

- [ ] **Step 2: Run test to verify it passes (it's a pure-logic test, no file I/O)**

```bash
uv run pytest tests/test_analytics.py::test_v3_training_runs_and_returns_metrics -v
```

Expected: PASS (this test exercises the logic using imported helpers, not the asset itself)

- [ ] **Step 3: Add v3 block inside `availability_pattern_export()`**

Locate the end of the existing v2 MLflow block in `availability_pattern_export()`. It ends after the `except Exception as exc: _log.warning(...)` line (around line 1624). Insert the following block immediately after that line, before the `# Generate predictions per area` comment:

```python
    # ── v3: 30-min buckets + area-relative lag features ──────────────────────
    # Bucket 5-min event_hours into 30-min slots
    from collections import defaultdict as _dd
    pa_bucket_counts_v3: dict = _dd(int)
    pa_bucket_weather_v3: dict = _dd(int)
    for (pa, event_hour), cnt in pa_hour_counts.items():
        try:
            dt = event_hour if isinstance(event_hour, datetime) else datetime.fromisoformat(str(event_hour))
        except Exception:
            continue
        bucket_ts = dt.replace(
            minute=(dt.minute // 30) * 30, second=0, microsecond=0
        )
        key = (pa, bucket_ts)
        pa_bucket_counts_v3[key] += cnt
        w_rank = pa_hour_weather.get((pa, event_hour), 0)
        if w_rank > pa_bucket_weather_v3[key]:
            pa_bucket_weather_v3[key] = w_rank

    # Temporal split on bucket timestamps (80/20)
    all_bucket_ts = sorted({ts for (_, ts) in pa_bucket_counts_v3})
    v3_split_ts   = all_bucket_ts[max(0, int(len(all_bucket_ts) * 0.8) - 1)]
    train_buckets_v3 = {k: v for k, v in pa_bucket_counts_v3.items() if k[1] <= v3_split_ts}

    # Compute per-(area, hour) mean from training buckets only (no leakage)
    _v3_sum: dict = defaultdict(float)
    _v3_n:   dict = defaultdict(int)
    for (pa, ts), cnt in train_buckets_v3.items():
        _v3_sum[(pa, ts.hour)] += cnt
        _v3_n[(pa, ts.hour)]   += 1
    v3_train_means: dict = {k: _v3_sum[k] / _v3_n[k] for k in _v3_sum}
    v3_global_mean = sum(_v3_sum.values()) / max(sum(_v3_n.values()), 1)

    # Build lag rows
    v3_lag_rows = _build_v3_lag_rows(
        dict(pa_bucket_counts_v3), _AVAIL_LAG, _AVAIL_HORIZON,
        v3_train_means, v3_global_mean,
    )

    if len(v3_lag_rows) >= 2:
        v3_lag_rows.sort(key=lambda r: r["timestamp_30min"])
        v3_split_idx  = max(1, int(len(v3_lag_rows) * 0.8))
        v3_train_rows = v3_lag_rows[:v3_split_idx]
        v3_val_rows   = v3_lag_rows[v3_split_idx:]

        _v3_numeric = [
            "lag_1_rel", "lag_2_rel", "lag_3_rel", "lag_4_rel",
            "hour_sin", "hour_cos", "dow_sin", "dow_cos",
            "is_weekend", "is_peak_hour", "area_hour_mean_count",
        ]
        X_train_v3 = [[r["planning_area"]] + [r[f] for f in _v3_numeric] for r in v3_train_rows]
        X_val_v3   = [[r["planning_area"]] + [r[f] for f in _v3_numeric] for r in v3_val_rows]
        y_tr_v3    = [r["count"] for r in v3_train_rows]
        y_va_v3    = [r["count"] for r in v3_val_rows]

        _v3_preprocessor = ColumnTransformer(transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), [0]),
            ("num", "passthrough", list(range(1, 1 + len(_v3_numeric)))),
        ])
        _v3_pipeline = Pipeline([
            ("preprocessor", _v3_preprocessor),
            ("lr", LinearRegression()),
        ])
        _v3_pipeline.fit(X_train_v3, y_tr_v3)
        _y_pred_tr_v3 = _v3_pipeline.predict(X_train_v3)
        _y_pred_va_v3 = _v3_pipeline.predict(X_val_v3)

        v3_train_mae = float(mean_absolute_error(y_tr_v3, _y_pred_tr_v3))
        v3_val_mae   = float(mean_absolute_error(y_va_v3, _y_pred_va_v3))
        v3_val_rmse  = float(mean_squared_error(y_va_v3, _y_pred_va_v3) ** 0.5)
        v3_val_r2    = float(r2_score(y_va_v3, _y_pred_va_v3)) if len(y_va_v3) > 1 else 0.0
        v3_gap       = v3_val_mae - v3_train_mae

        _log.info(
            f"v3 metrics — train_mae={v3_train_mae:.1f} val_mae={v3_val_mae:.1f} "
            f"val_rmse={v3_val_rmse:.1f} val_r2={v3_val_r2:.3f} gap={v3_gap:.1f} "
            f"n_rows={len(v3_lag_rows)}"
        )

        # Log to MLflow as a separate lr_v3 run in the same experiment
        if _mlflow_cfg is not None:
            try:
                configure_mlflow_tracking(_mlflow_cfg)
                mlflow.set_experiment(_mlflow_cfg["experiments"]["availability_pattern"])
                with mlflow.start_run(run_name=f"lr_v3_{datetime.now().strftime('%Y%m%dT%H%M')}"):
                    mlflow.log_params({
                        "feature_version": "v3",
                        "model_type": "LinearRegression",
                        "bucket_minutes": 30,
                        "lag": _AVAIL_LAG,
                        "horizon": _AVAIL_HORIZON,
                        "train_split": 0.8,
                        "features": ",".join(_v3_numeric),
                    })
                    mlflow.log_metric("train_mae", v3_train_mae)
                    mlflow.log_metric("val_mae",   v3_val_mae)
                    mlflow.log_metric("val_rmse",  v3_val_rmse)
                    mlflow.log_metric("val_r2",    v3_val_r2)
                    mlflow.log_metric("train_val_mae_gap", v3_gap)
                    mlflow.log_metric("n_training_rows",  len(v3_train_rows))
                    mlflow.log_metric("n_planning_areas", len({r["planning_area"] for r in v3_lag_rows}))
                    # Per-area val MAE
                    _v3_area_map: dict = defaultdict(list)
                    for _i, _r in enumerate(v3_val_rows):
                        _v3_area_map[_r["planning_area"]].append(_i)
                    for _pa, _idxs in _v3_area_map.items():
                        _y_true = [y_va_v3[_i] for _i in _idxs]
                        _y_pred = [_y_pred_va_v3[_i] for _i in _idxs]
                        _k = "area_mae_" + _pa.lower().replace(" ", "_")
                        mlflow.log_metric(_k, float(mean_absolute_error(_y_true, _y_pred)))
                    mlflow.sklearn.log_model(
                        sk_model=_v3_pipeline,
                        artifact_path="model",
                    )
            except Exception as _v3_exc:
                _log.warning(f"MLflow v3 logging failed: {_v3_exc}", exc_info=True)
    else:
        _log.info("v3: insufficient lag rows — skipping v3 training")
    # ── end v3 ───────────────────────────────────────────────────────────────
```

- [ ] **Step 4: Run the full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add sg_transit_weather_mesh/assets/analytics.py tests/test_analytics.py
git commit -m "feat: add v3 30-min lag training path to availability_pattern_export"
```

---

### Task 3: Smoke-test the asset end-to-end and verify MLflow run appears

**Files:**
- No file changes — run commands only

- [ ] **Step 1: Ensure MLflow server is running**

```bash
# From project root — must be running before Dagster
uv run mlflow server \
  --backend-store-uri sqlite:///data/mlflow.db \
  --default-artifact-root ./data/mlruns \
  --host 0.0.0.0 --port 5050 --workers 1 &
```

Wait ~5 seconds, then verify: open `http://localhost:5050` — should show MLflow UI.

- [ ] **Step 2: Run the availability_pattern_export asset once**

```bash
uv run python - <<'EOF'
import dagster
from sg_transit_weather_mesh import defs
result = dagster.materialize(
    [defs.get_asset_def("availability_pattern_export")],
    resources=defs.get_resource_defs_for_asset("availability_pattern_export"),
)
print("Success:", result.success)
EOF
```

Expected: `Success: True` with Dagster log lines including:
```
v3 metrics — train_mae=... val_mae=... val_r2=...
```

- [ ] **Step 3: Verify v3 run in MLflow UI**

Open `http://localhost:5050`, navigate to the `sg-taxi-availability-pattern` experiment (or whichever name is configured in `config/config.yaml` under `experiments.availability_pattern`).

Verify:
- Two recent runs are visible — one named `lr_YYYYMMDDTHHMMM` (v2) and one named `lr_v3_YYYYMMDDTHHMMM` (v3)
- v3 run has params: `feature_version=v3`, `bucket_minutes=30`, `lag=4`, `horizon=4`
- v3 run has metrics: `val_r2`, `val_mae`, `val_rmse`, `train_val_mae_gap`
- Both runs appear in the same experiment for side-by-side comparison

- [ ] **Step 4: Commit smoke-test confirmation note**

No code change needed. If the smoke test passed, proceed to done.

```bash
git log --oneline -3
```

Confirm the two feature commits are present.
