# Availability Pattern Feature Engineering — Design Spec

**Date:** 2026-06-26  
**Status:** Approved  
**Scope:** `availability_pattern_export()` in `sg_transit_weather_mesh/assets/analytics.py`

---

## Problem

After implementing `is_peak_hour` and `weather_intensity` features, the Ridge model still underfits severely:

| Metric | Current (feature v1) | Target (feature v2) |
|--------|---------------------|---------------------|
| train_mae | 182.5 | < 80 |
| val_mae | 319.0 | < 100 |
| val_r2 | 0.29 | > 0.70 |
| val_rmse | 1002.6 | < 200 |
| train_val_mae_gap | 136.5 | < 50 |

**Root cause:** Linear regression with only cyclic time features + weather cannot learn the absolute scale of taxi counts per area. Orchard at 18:00 has ~10× more taxis than Lim Chu Kang — this is not encoded in the current features. The model has no historical count anchor per area-hour, so it cannot learn area-specific baselines.

**Insight from reference script (`train_linear_regression_mlflow.py`):** Including `current_taxi_count` dramatically improves linear model accuracy by providing a direct scale anchor. We apply the same principle using a training-derived historical mean rather than a live snapshot count.

---

## Approach: Add `area_hour_mean_count` Feature (Feature v2)

Single change to `availability_pattern_export()`. Replace `Ridge` with `LinearRegression`. Add one new feature. No changes to `pattern.json` schema, pipeline graph, or frontend.

---

## Data Flow

```
DuckDB rows
  → aggregate by (planning_area, event_hour)
  → temporal 80/20 split
  → compute area_hour_mean_count from train rows only   ← NEW (no leakage)
  → attach mean_count to each row (train, val, inference)
  → LinearRegression (replaces Ridge)
  → predict
```

---

## Feature Matrix

**v1 (current):**
```
planning_area (OHE), hour_sin, hour_cos, dow_sin, dow_cos,
is_weekend, is_peak_hour, weather_intensity
```

**v2 (new):**
```
planning_area (OHE), hour_sin, hour_cos, dow_sin, dow_cos,
is_weekend, is_peak_hour, weather_intensity, area_hour_mean_count
```

---

## Implementation

**Step 1 — Compute means from training split only (after `split_idx`, before building `X_train_full`):**

```python
from collections import defaultdict
_area_hour_sum: dict[tuple, float] = defaultdict(float)
_area_hour_n: dict[tuple, int] = defaultdict(int)
for r in train_rows:
    key = (r["planning_area"], r["event_hour"].hour)
    _area_hour_sum[key] += r["count"]
    _area_hour_n[key] += 1
area_hour_mean: dict[tuple, float] = {
    k: _area_hour_sum[k] / _area_hour_n[k] for k in _area_hour_sum
}
global_mean = (
    sum(_area_hour_sum.values()) / max(sum(_area_hour_n.values()), 1)
)
```

**Step 2 — Add to feature row building (both train and val):**

```python
area_hour_mean_count = area_hour_mean.get(
    (r["planning_area"], r["event_hour"].hour), global_mean
)
# append to the numeric feature vector
```

**Step 3 — Update `numeric_features`:**

```python
numeric_features = [
    "hour_sin", "hour_cos", "dow_sin", "dow_cos",
    "is_weekend", "is_peak_hour", "weather_intensity",
    "area_hour_mean_count",  # NEW
]
```

**Step 4 — Replace model:**

```python
# Before:
Pipeline([("preprocessor", preprocessor), ("ridge", Ridge(alpha=1.0))])
# After:
Pipeline([("preprocessor", preprocessor), ("lr", LinearRegression())])
```

With a strong scale anchor, regularisation shrinkage is no longer needed.

**Step 5 — Inference lookup (both prediction loops):**

```python
mean_count = area_hour_mean.get((pa, h), global_mean)
# include mean_count in the feature vector for pipeline.predict()
```

---

## MLflow Changes

Add to existing `log_params`:
```python
mlflow.log_param("feature_version", "v2")
mlflow.log_param("model_type", "LinearRegression")
mlflow.log_param("lag_feature", "area_hour_mean_count")
```

All existing metrics (`train_mae`, `val_mae`, `val_rmse`, `val_r2`, `train_val_mae_gap`) remain unchanged — comparable across runs. Champion selection logic and `_CHAMPION_GAP_THRESHOLD` unchanged.

---

## What Does Not Change

| Item | Reason |
|---|---|
| `pattern.json` schema | Predictions still integer taxi counts |
| `sufficient_data` threshold (48 hours) | No reason to change |
| Champion guardrail `_CHAMPION_GAP_THRESHOLD` | Stays; gap expected to narrow naturally |
| MLflow registration, versioning, alias logic | Unchanged |
| All other Dagster assets | Unchanged |
| Frontend | Unchanged |

---

## Verification

1. Ensure mart data exists: `uv run dagster job execute -j sg_taxi_weather_sync_job`
2. Materialize `availability_pattern_export` via Dagster UI or CLI.
3. Open MLflow at `http://localhost:5050` → experiment `sg-taxi-availability-pattern`.
4. Compare v1 vs v2 runs on `val_mae`, `val_r2`, `train_val_mae_gap`.
5. Confirm `pattern.json` is written with valid predictions for all planning areas.
6. Run `uv run pytest tests -v` — no regressions.

---

## Files Affected

- `sg_transit_weather_mesh/assets/analytics.py` — `availability_pattern_export()` only
