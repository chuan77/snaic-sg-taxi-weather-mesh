# Design: Champion Selection for `sg-taxi-availability-pattern`

**Date:** 2026-06-25
**Asset:** `availability_pattern_export`
**Experiment:** `sg-taxi-availability-pattern`
**Registered model:** `TaxiAvailabilityPattern`

---

## Problem

Every run of `availability_pattern_export` registers its Ridge model to the MLflow Model Registry unconditionally. There is no mechanism to identify which version is the best-performing model or to surface it for serving.

---

## Goal

After each training run, perform a champion selection process:
- Promote the new model to `@champion` if it is better than the current champion.
- Guard against overfitting using a `train_val_mae_gap` threshold.
- Tag each run with the outcome for full auditability in MLflow.

---

## Champion Criterion

**Primary metric:** `val_mae` (lower is better)

**Guardrail:** `train_val_mae_gap ≤ 20` taxis

> Rationale: Ridge (α=1.0) is already regularised, so gaps above 20 taxis (~10–15% of typical per-area counts of 20–150) indicate the model over-fit to a specific training period and should not be promoted.

---

## Approach: MLflow Alias `@champion`

The MLflow Model Registry supports named aliases per registered model. Only one version can hold a given alias at a time — the registry enforces uniqueness. This is the MLflow-native champion/challenger pattern.

The serving layer (FastAPI `ModelStore`) currently loads by registered model name. It can optionally be updated in a future iteration to resolve `@champion` specifically; this design does not change `ModelStore`.

---

## Decision Logic

```
train_val_mae_gap > 20
    → tag run: champion_skipped=guardrail_failed
    → skip promotion

train_val_mae_gap ≤ 20 AND no existing @champion
    → promote (first-ever champion)
    → tag run: champion_promoted=true

train_val_mae_gap ≤ 20 AND new val_mae < current champion val_mae
    → promote (better model found)
    → tag run: champion_promoted=true, champion_val_mae=<previous>

train_val_mae_gap ≤ 20 AND new val_mae ≥ current champion val_mae
    → do not promote
    → tag run: champion_promoted=false, champion_val_mae=<current>
```

---

## Code Changes

All changes are confined to the MLflow block inside `availability_pattern_export` in `sg_transit_weather_mesh/assets/analytics.py`.

### New module-level constant

```python
_CHAMPION_GAP_THRESHOLD = 20  # taxis; guardrail for train_val_mae_gap
```

### Helper (inline, not a separate function)

`_get_champion_val_mae(client, model_name)` — queries the `@champion` alias on `model_name`, fetches the run's `val_mae` metric. Returns `None` if no champion alias exists yet.

### Updated MLflow block structure

```
1. configure_mlflow_tracking / set_experiment    [unchanged]
2. start_run                                     [unchanged]
3. log_params / log_metrics                      [unchanged]
4. log_model → capture MlflowClient + version    [minor: capture return]
5. [NEW] guardrail check
6. [NEW] fetch @champion val_mae via MlflowClient
7. [NEW] compare → set_registered_model_alias if better
8. [NEW] tag run with champion_promoted / champion_skipped / champion_val_mae
```

### Run tags written

| Tag key | Values | Meaning |
|---|---|---|
| `champion_promoted` | `"true"` / `"false"` | Whether this run became champion |
| `champion_skipped` | `"guardrail_failed"` | Set only when gap > threshold |
| `champion_val_mae` | float string | Previous champion's val_mae (for comparison context) |

---

## Out of Scope

- Changes to `pattern.json` schema or downstream assets — unaffected; they always use the in-memory `pipeline`.
- Changes to `ModelStore` or FastAPI — `@champion` alias support deferred to a future iteration.
- `config.yaml` — threshold hardcoded as `_CHAMPION_GAP_THRESHOLD`; externalising it is future work.
- Any change to the `demand_forecast_export` asset or other experiments.

---

## Testing

Existing `tests/test_analytics.py` covers Ridge training helpers. New unit tests (to be added in the implementation plan) should cover:

- `_get_champion_val_mae` returns `None` when no alias exists.
- `_get_champion_val_mae` returns correct float when alias exists.
- Guardrail path: gap > 20 → no alias assignment, correct tags.
- First-champion path: no existing champion → alias assigned.
- Better-model path: new val_mae < current → alias reassigned.
- No-promotion path: new val_mae ≥ current → alias unchanged, tags correct.
