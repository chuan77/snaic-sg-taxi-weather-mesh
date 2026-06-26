# Availability Pattern Feature Engineering — Design Spec

**Date:** 2026-06-26  
**Status:** Approved  
**Scope:** `availability_pattern_export()` in `sg_transit_weather_mesh/assets/analytics.py`

---

## Problem

The `TaxiAvailabilityPattern` Ridge model produces poor predictions:

- `val_mae = 279.8`, `train_mae = 183.7`, `val_r2 = 0.39`
- `train_val_mae_gap = 96.1` exceeds the `_CHAMPION_GAP_THRESHOLD = 20` guardrail
- Per-area MAE varies wildly: Lim Chu Kang = 79, Changi = 1,294, Downtown Core = 893

Root cause: Ridge minimises absolute error, so high-traffic areas (Changi, Downtown Core, Bukit Merah) dominate the loss function during training. The model overfits their large-count patterns and fits smaller areas poorly. This is a model architecture problem — waiting for more data will reduce the gap somewhat but will not fix the high `train_mae` or the per-area imbalance.

---

## Approach: Feature Engineering (Option B)

Three targeted changes to `availability_pattern_export()`. No changes to the pipeline graph, `pattern.json` schema, MLflow registration flow, or frontend.

---

## Change 1: Log-transform the Target

**Why:** `log1p(count)` normalises the scale difference between high-traffic and low-traffic planning areas. Ridge then fits proportional errors rather than absolute ones, giving each of the 53 areas equal weight regardless of traffic volume.

**Training:**
- Replace `y = [r["count"] for r in rows_list]` with `y = [math.log1p(r["count"]) for r in rows_list]`
- After `pipeline.predict()`, apply `math.expm1()` to both train and val predictions before computing MAE, RMSE, and R²
- MLflow metrics (`train_mae`, `val_mae`, `train_val_mae_gap`) remain in original taxi-count units so the `_CHAMPION_GAP_THRESHOLD = 20` guardrail stays interpretable

**Inference:**
- Apply `math.expm1(pipeline.predict(feat)[0])` before `int(round(...))` in both the predictions loop (lines 1596–1605) and the low-availability hours loop (lines 1613–1622)

---

## Change 2: Add `is_peak_hour` Feature

**Why:** Singapore rush hours (morning peak 07:00–09:00, evening peak 17:00–19:00) drive consistent demand spikes across most planning areas. A binary flag is a stable, generalising signal that repeats every weekday regardless of data gaps.

**Values:** 1 if `hour ∈ {7, 8, 17, 18, 19}`, else 0  
**Added to:** `numeric_features` list and every feature row dict  
**Inference:** Computed from `target_dt.hour` — no DB access needed

---

## Change 3: Add `weather_intensity` Feature

**Why:** Precipitation suppresses taxi availability in residential areas and spikes demand near transport hubs. The mart already stores `prominent_weather_condition` per grid cell per hour — this signal is free to use.

**Training:** Extend the SQL query to also select `t.prominent_weather_condition`. Map through the existing `FORECAST_INTENSITY` + `INTENSITY_RANK` dicts already in the codebase:

| Condition | `weather_intensity` |
|---|---|
| Fair / Cloudy (and NULL) | 0 |
| Light Rain / Light Showers | 1 |
| Moderate Rain | 2 |
| Heavy Rain / Thundery Showers | 3 |

NULL rows (no NEA forecast joined) default to 0.

**Inference:** In the same DB connection already open at the start of the asset, run one additional query to fetch the most recent `prominent_weather_condition` from the mart. Map to 0–3 and use that single value for all four prediction horizons (now, +30min, +1h, +2h). Future-hour weather is unknown; using current conditions is consistent with how the rest of the dashboard uses nowcast data and is far better than ignoring weather entirely.

---

## MLflow Changes

- Add `features` param: comma-separated list of the full feature set, so each run is self-documenting
- `train_mae`, `val_mae`, `val_rmse`, `val_r2`, `train_val_mae_gap` all remain in original taxi-count units
- No changes to champion selection logic or `_CHAMPION_GAP_THRESHOLD`

---

## What Does Not Change

| Item | Reason |
|---|---|
| One global Ridge model across 53 areas | Per-area models (Option C) deferred until 2–3 weeks of data |
| `Ridge(alpha=1.0)` | Log-transform provides the real regularisation gain; no tuning needed yet |
| `pattern.json` schema | Predictions are still integer taxi counts; frontend requires no changes |
| `sufficient_data` threshold (48 hours) | No reason to change |
| Champion guardrail `_CHAMPION_GAP_THRESHOLD = 20` | Stays; gap should naturally improve after log-transform |
| MLflow registration, versioning, alias logic | Unchanged |
| All other Dagster assets | Unchanged |

---

## Expected Outcome

- `val_mae` should drop from ~280 to the 80–120 range (log-transform levels the playing field across areas)
- `val_r2` should improve from 0.39 to 0.65–0.75
- `train_val_mae_gap` should narrow; whether it passes the guardrail depends on accumulated data
- Per-area MAEs for Changi, Downtown Core, Bukit Merah should fall dramatically; small-area MAEs (Lim Chu Kang, Tengah) should hold steady or improve slightly

---

## Files Affected

- `sg_transit_weather_mesh/assets/analytics.py` — `availability_pattern_export()` only
