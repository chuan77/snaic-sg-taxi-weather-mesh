# Availability Pattern — 30-min Bucketing + Area-Relative Lag Features (v3)

**Date:** 2026-06-27
**Status:** Approved
**Scope:** `availability_pattern_export()` in `sg_transit_weather_mesh/assets/analytics.py`

---

## Problem

LR v2 (`area_hour_mean_count` feature, `val_r2 = 0.67`, `val_mae = 199.6`) improved significantly over v1 but has a structural limitation: the model projects forward by shifting time features, not by learning from a true lag sequence. The +2h prediction is the same linear function evaluated at a future timestamp — it has no memory of recent trends.

Additionally, a single global model trained on raw counts suffers from scale imbalance: Changi buckets (~800 taxis) dominate gradient updates, leaving low-traffic areas (Tengah, ~15 taxis) poorly fitted. Raw log1p transform was previously tried and reverted (commit `7e5c37d`).

---

## Goal

MLflow experiment only — compare v3 against v2 in the existing `availability_pattern` experiment. No changes to `pattern.json`, frontend, or Dagster asset graph.

---

## Approach: 30-min Buckets + Area-Relative Lag Features (v3)

### Data Transformation

Aggregate 5-min `fct_taxi_weather_trends` rows into 30-min buckets:

```
timestamp_30min = floor(event_hour, 30 minutes)
GROUP BY (planning_area, timestamp_30min)
  → SUM(available_taxis_count)  → taxi_count
  → MAX(weather_intensity)       → dominant weather
```

Each bucket represents ~6 raw rows. Result: ~48 observations per area per day. Minimum qualifying samples per area to contribute lag rows: LAG + HORIZON + 1 = 9 buckets (~4.5 hours).

### Lag Matrix Construction

Constants (local to the v3 block):
```python
_AVAIL_LAG     = 4   # 2 hours of history at 30-min granularity
_AVAIL_HORIZON = 4   # predict 2 hours ahead
```

For each planning area, sort rows by `timestamp_30min` and build:

```
lag_k_rel = count[t - k] / area_mean    (for k = 1..4)
```

where `area_mean` is computed from training rows only (no leakage), falling back to global mean for unseen areas.

### Feature Matrix (v3)

```
planning_area (OHE)
lag_1_rel, lag_2_rel, lag_3_rel, lag_4_rel   ← area-relative lags (momentum)
hour_sin, hour_cos                            ← cyclic hour
dow_sin, dow_cos                              ← cyclic day-of-week
is_weekend, is_peak_hour                      ← binary time context
weather_intensity                             ← 0–4 ordinal
area_hour_mean_count                          ← absolute scale anchor (from v2)
```

**Target:** raw `count` at `timestamp_30min + 4` (absolute taxis, not normalised).

**Model:** `LinearRegression` — same as v2 for clean comparison. GBR can be the next experiment if v3 validates.

---

## MLflow Tracking

- **Experiment:** existing `availability_pattern` experiment (same name, same registry)
- **Run name:** `lr_v3_YYYYMMDDTHHMMM`
- **Params logged:** `feature_version=v3`, `model_type=LinearRegression`, `bucket_minutes=30`, `lag=4`, `horizon=4`, `train_split=0.8`
- **Metrics logged:** `train_mae`, `val_mae`, `val_rmse`, `val_r2`, `train_val_mae_gap`, `n_training_rows`, `n_planning_areas`, per-area `area_mae_*`
- **Registered model:** no promotion — v3 is an experiment run only. Promotion is out of scope.

v2 and v3 runs sit side-by-side in the MLflow UI for direct metric comparison.

---

## What Does Not Change

| Component | Status |
|---|---|
| `pattern.json` schema | Unchanged |
| Dagster asset / schedule | Unchanged |
| Frontend | Unchanged |
| `_FORECAST_LAG`, `_FORECAST_HORIZON` | Unchanged (GBR demand forecast constants) |
| v2 training path | Unchanged (v3 is additive code inside the same asset) |

---

## Data Flow

```
DuckDB fct_taxi_weather_trends (5-min rows)
  → bucket to 30-min intervals (Python floor)
  → sort by (planning_area, timestamp_30min)
  → temporal 80/20 split
  → compute area_mean from train rows only
  → build lag_k_rel = count[t-k] / area_mean  (no leakage)
  → attach area_hour_mean_count (from v2, train-derived)
  → LinearRegression fit
  → log metrics + model to MLflow as lr_v3 run
```

---

## Success Criteria

| Metric | v2 baseline | v3 target |
|---|---|---|
| val_r2 | 0.67 | > 0.75 |
| val_mae | 199.6 | < 150 |
| val_rmse | 387.9 | < 300 |
| train_val_mae_gap | ~108 | < 80 |

---

## Out of Scope

- Per-area models (Option B) — next experiment if v3 validates
- Multi-horizon outputs (separate model per horizon)
- Promoting v3 to `pattern.json` production output
- Frontend changes
