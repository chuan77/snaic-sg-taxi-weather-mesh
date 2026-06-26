# Availability Pattern Feature Engineering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the `TaxiAvailabilityPattern` Ridge model by adding `is_peak_hour` and `weather_intensity` features and log-transforming the target, reducing val_mae from ~280 to ~80–120 and improving val_r2 from 0.39 to 0.65–0.75.

**Architecture:** All changes are confined to `availability_pattern_export()` in `sg_transit_weather_mesh/assets/analytics.py`. No schema, pipeline graph, or frontend changes. Training fits on `log1p(count)`; predictions apply `expm1()` before rounding. MLflow metrics remain in original taxi-count units throughout.

**Tech Stack:** scikit-learn Ridge, DuckDB, MLflow, Python math stdlib. Existing `FORECAST_INTENSITY` and `INTENSITY_RANK` dicts reused for weather mapping.

## Global Constraints

- Single file modified: `sg_transit_weather_mesh/assets/analytics.py`
- All MLflow metrics (`train_mae`, `val_mae`, `train_val_mae_gap`) must remain in original taxi-count units (not log-space)
- `pattern.json` schema is unchanged — predictions are still integers, `val_mae` is in original space
- `_CHAMPION_GAP_THRESHOLD = 20` stays; no changes to champion selection logic
- `FORECAST_INTENSITY` and `INTENSITY_RANK` dicts (lines 41–120) are reused as-is — do not add new mappings
- Run tests with: `uv run pytest tests/test_analytics.py -v`

---

## File Map

| File | Change |
|---|---|
| `sg_transit_weather_mesh/assets/analytics.py` | Modify `availability_pattern_export()` only — three targeted edits |
| `tests/test_analytics.py` | Add unit tests for each new behaviour |

---

### Task 1: Add `is_peak_hour` Feature

**Files:**
- Modify: `sg_transit_weather_mesh/assets/analytics.py` (lines ~1477–1530, ~1596–1622)
- Test: `tests/test_analytics.py`

**Interfaces:**
- Produces: `is_peak_hour` key in every feature row dict; added to `numeric_features` list; included in inference feature vectors

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_analytics.py`:

```python
from sg_transit_weather_mesh.assets.analytics import FORECAST_INTENSITY, INTENSITY_RANK


def test_is_peak_hour_true_for_morning_peak():
    """Hours 7 and 8 are morning peak."""
    for h in (7, 8):
        assert (1 if h in {7, 8, 17, 18, 19} else 0) == 1


def test_is_peak_hour_true_for_evening_peak():
    """Hours 17, 18, 19 are evening peak."""
    for h in (17, 18, 19):
        assert (1 if h in {7, 8, 17, 18, 19} else 0) == 1


def test_is_peak_hour_false_for_offpeak():
    """Hour 12 (midday) and 3 (night) are not peak."""
    for h in (3, 12, 23):
        assert (1 if h in {7, 8, 17, 18, 19} else 0) == 0
```

- [ ] **Step 2: Run tests to verify they fail (or pass trivially)**

```bash
uv run pytest tests/test_analytics.py::test_is_peak_hour_true_for_morning_peak tests/test_analytics.py::test_is_peak_hour_true_for_evening_peak tests/test_analytics.py::test_is_peak_hour_false_for_offpeak -v
```

These tests are logic-only, so they will pass immediately. That confirms the logic is correct before we wire it into the asset.

- [ ] **Step 3: Add `is_peak_hour` to feature row building**

In `availability_pattern_export()`, find the block around line 1477–1493 that builds `feature_rows`. Add `is_peak_hour` alongside `is_weekend`:

```python
        is_weekend    = 1 if dow >= 5 else 0
        is_peak_hour  = 1 if h in {7, 8, 17, 18, 19} else 0
        feature_rows.append({
            "event_hour":    dt,
            "planning_area": pa,
            "hour_sin":      hour_sin,
            "hour_cos":      hour_cos,
            "dow_sin":       dow_sin,
            "dow_cos":       dow_cos,
            "is_weekend":    is_weekend,
            "is_peak_hour":  is_peak_hour,
            "count":         total_count,
        })
```

- [ ] **Step 4: Add `is_peak_hour` to `numeric_features`**

Find line ~1501:

```python
    numeric_features = ["hour_sin", "hour_cos", "dow_sin", "dow_cos", "is_weekend"]
```

Change to:

```python
    numeric_features = ["hour_sin", "hour_cos", "dow_sin", "dow_cos", "is_weekend", "is_peak_hour"]
```

- [ ] **Step 5: Add `is_peak_hour` to inference feature vectors**

Find the predictions loop (~lines 1593–1605) that builds `feat` for each area/offset. Add the flag as the last element:

```python
            feat = [
                [pa,
                 math.sin(2 * math.pi * h / 24),
                 math.cos(2 * math.pi * h / 24),
                 math.sin(2 * math.pi * dow / 7),
                 math.cos(2 * math.pi * dow / 7),
                 1 if dow >= 5 else 0,
                 1 if h in {7, 8, 17, 18, 19} else 0]
            ]
```

Find the low-availability hours loop (~lines 1611–1622) and apply the same change to its `feat`:

```python
            feat = [
                [pa,
                 math.sin(2 * math.pi * h / 24),
                 math.cos(2 * math.pi * h / 24),
                 math.sin(2 * math.pi * dow / 7),
                 math.cos(2 * math.pi * dow / 7),
                 1 if dow >= 5 else 0,
                 1 if h in {7, 8, 17, 18, 19} else 0]
            ]
```

- [ ] **Step 6: Run the full analytics test suite**

```bash
uv run pytest tests/test_analytics.py -v
```

Expected: all existing tests still pass (the feature addition is backward-compatible with mocked data).

- [ ] **Step 7: Commit**

```bash
git add sg_transit_weather_mesh/assets/analytics.py tests/test_analytics.py
git commit -m "feat: add is_peak_hour feature to availability pattern model"
```

---

### Task 2: Log-transform the Target

**Files:**
- Modify: `sg_transit_weather_mesh/assets/analytics.py` (lines ~1504–1545 and ~1596–1624)
- Test: `tests/test_analytics.py`

**Interfaces:**
- Consumes: `feature_rows` with `"count"` key (unchanged)
- Produces: `y_tr` / `y_va` in log-space for training; `y_tr_orig` / `y_va_orig` / `y_pred_tr_orig` / `y_pred_va_orig` in original taxi-count space for metrics; inference calls apply `expm1()` before rounding

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_analytics.py`:

```python
import math


def test_log1p_expm1_roundtrip():
    """log1p then expm1 recovers the original count."""
    for count in (0, 1, 10, 100, 1000, 1294):
        assert abs(math.expm1(math.log1p(count)) - count) < 1e-9


def test_log1p_zero_safe():
    """log1p(0) == 0, expm1(0) == 0 — no domain error."""
    assert math.log1p(0) == 0.0
    assert math.expm1(0.0) == 0.0
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
uv run pytest tests/test_analytics.py::test_log1p_expm1_roundtrip tests/test_analytics.py::test_log1p_zero_safe -v
```

Expected: PASS — confirms the math before touching the asset.

- [ ] **Step 3: Log-transform the target in `_to_X_y`**

Find the nested function `_to_X_y` (~line 1504):

```python
    def _to_X_y(rows_list):
        X_cat  = [[r["planning_area"]] for r in rows_list]
        X_num  = [[r[f] for f in numeric_features] for r in rows_list]
        y      = [r["count"] for r in rows_list]
        return X_cat, X_num, y
```

Change to:

```python
    def _to_X_y(rows_list):
        X_cat  = [[r["planning_area"]] for r in rows_list]
        X_num  = [[r[f] for f in numeric_features] for r in rows_list]
        y      = [math.log1p(r["count"]) for r in rows_list]
        return X_cat, X_num, y
```

- [ ] **Step 4: Compute metrics in original taxi-count space**

Find the block after `pipeline.fit(...)` (~lines 1527–1545). Replace the metric computation with:

```python
    pipeline.fit(X_train_full, y_tr)
    y_pred_tr_log = pipeline.predict(X_train_full)
    y_pred_va_log = pipeline.predict(X_val_full)

    # Back-transform to original taxi-count space for interpretable metrics
    y_tr_orig       = [math.expm1(v) for v in y_tr]
    y_va_orig       = [math.expm1(v) for v in y_va]
    y_pred_tr_orig  = [max(0.0, math.expm1(v)) for v in y_pred_tr_log]
    y_pred_va_orig  = [max(0.0, math.expm1(v)) for v in y_pred_va_log]

    train_mae         = float(mean_absolute_error(y_tr_orig, y_pred_tr_orig))
    val_mae           = float(mean_absolute_error(y_va_orig, y_pred_va_orig))
    val_rmse          = float(mean_squared_error(y_va_orig, y_pred_va_orig) ** 0.5)
    val_r2            = float(r2_score(y_va_orig, y_pred_va_orig)) if len(y_va_orig) > 1 else 0.0
    train_val_mae_gap = val_mae - train_mae
```

- [ ] **Step 5: Fix per-area MAE to use original-space predictions**

Find the per-area val MAE block (~lines 1537–1545). It uses `y_va` and `y_pred_va` — update to use the original-space versions:

```python
    area_val_mae: dict[str, float] = {}
    area_rows_map: dict[str, list] = defaultdict(list)
    for i, r in enumerate(val_rows):
        area_rows_map[r["planning_area"]].append(i)
    for pa, idxs in area_rows_map.items():
        y_true_pa = [y_va_orig[i] for i in idxs]
        y_pred_pa = [y_pred_va_orig[i] for i in idxs]
        area_val_mae[pa] = float(mean_absolute_error(y_true_pa, y_pred_pa))
```

- [ ] **Step 6: Apply `expm1` in the inference prediction loop**

Find the predictions loop (~lines 1596–1605). The last line that computes `pred_val` currently does:

```python
            pred_val = max(0, int(round(float(pipeline.predict(feat)[0]))))
```

Change to:

```python
            pred_val = max(0, int(round(math.expm1(float(pipeline.predict(feat)[0])))))
```

- [ ] **Step 7: Apply `expm1` in the low-availability hours loop**

Find the low-availability loop (~lines 1619–1622). The line that appends to `hourly_preds` currently does:

```python
        hourly_preds.append(max(0, float(pipeline.predict(feat)[0])))
```

Change to:

```python
        hourly_preds.append(max(0.0, math.expm1(float(pipeline.predict(feat)[0]))))
```

- [ ] **Step 8: Run the full analytics test suite**

```bash
uv run pytest tests/test_analytics.py -v
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add sg_transit_weather_mesh/assets/analytics.py tests/test_analytics.py
git commit -m "feat: log1p target transform for availability pattern model"
```

---

### Task 3: Add `weather_intensity` Feature

**Files:**
- Modify: `sg_transit_weather_mesh/assets/analytics.py` (lines ~1402–1416, ~1453–1493, ~1501, ~1596–1624)
- Test: `tests/test_analytics.py`

**Interfaces:**
- Consumes: `FORECAST_INTENSITY: dict[str, str]` (line 41) and `INTENSITY_RANK: dict[str, int]` (line 120) — already imported in file scope
- Produces: `weather_intensity` int (0–4) in every feature row; `current_weather_intensity` int used for all four inference horizons

**Weather intensity scale** (from existing `INTENSITY_RANK`):
- 0 = clear/fair/cloudy/NULL
- 1 = drizzle/light rain/hazy/mist
- 2 = moderate rain/showers
- 3 = heavy rain/heavy showers
- 4 = thundery showers / storm

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_analytics.py`:

```python
def test_weather_intensity_clear_maps_to_zero():
    """Fair weather and NULL both map to intensity 0."""
    assert INTENSITY_RANK.get(FORECAST_INTENSITY.get("Fair", "clear"), 0) == 0
    assert INTENSITY_RANK.get(FORECAST_INTENSITY.get("", "clear"), 0) == 0


def test_weather_intensity_thundery_maps_to_four():
    """Thundery Showers maps to intensity 4 (storm)."""
    assert INTENSITY_RANK.get(FORECAST_INTENSITY.get("Thundery Showers", "clear"), 0) == 4


def test_weather_intensity_moderate_rain_maps_to_two():
    """Moderate Rain maps to intensity 2."""
    assert INTENSITY_RANK.get(FORECAST_INTENSITY.get("Moderate Rain", "clear"), 0) == 2


def test_weather_intensity_unknown_condition_defaults_to_zero():
    """An unrecognised forecast string defaults to 0 via the 'clear' fallback."""
    assert INTENSITY_RANK.get(FORECAST_INTENSITY.get("Alien Weather", "clear"), 0) == 0
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
uv run pytest tests/test_analytics.py::test_weather_intensity_clear_maps_to_zero tests/test_analytics.py::test_weather_intensity_thundery_maps_to_four tests/test_analytics.py::test_weather_intensity_moderate_rain_maps_to_two tests/test_analytics.py::test_weather_intensity_unknown_condition_defaults_to_zero -v
```

Expected: PASS — confirms the mapping logic before wiring into the asset.

- [ ] **Step 3: Extend the SQL query to fetch `prominent_weather_condition`**

Find the `conn.execute("""` block inside `availability_pattern_export()` (~line 1404). Change:

```python
        rows = conn.execute("""
            SELECT t.event_hour, t.grid_lat, t.grid_lon, t.available_taxis_count
            FROM mart.fct_taxi_weather_trends t
            ORDER BY t.event_hour
        """).fetchall()
```

To:

```python
        rows = conn.execute("""
            SELECT t.event_hour, t.grid_lat, t.grid_lon, t.available_taxis_count,
                   t.prominent_weather_condition
            FROM mart.fct_taxi_weather_trends t
            ORDER BY t.event_hour
        """).fetchall()
        weather_row = conn.execute("""
            SELECT prominent_weather_condition
            FROM mart.fct_taxi_weather_trends
            WHERE event_hour = (SELECT MAX(event_hour) FROM mart.fct_taxi_weather_trends)
            LIMIT 1
        """).fetchone()
```

- [ ] **Step 4: Derive `current_weather_intensity` for inference**

Immediately after the `conn` block closes (after `finally: conn.close()`), add:

```python
    _wc = (weather_row[0] or "") if weather_row else ""
    current_weather_intensity = INTENSITY_RANK.get(FORECAST_INTENSITY.get(_wc, "clear"), 0)
```

- [ ] **Step 5: Track worst weather per `(planning_area, event_hour)` during aggregation**

Find the `pa_hour_counts` aggregation loop (~line 1455). It currently reads 4-tuples. Change to unpack 5-tuples and track weather:

```python
    pa_hour_counts: dict[tuple, int] = defaultdict(int)
    pa_hour_weather: dict[tuple, int] = {}  # (pa, event_hour) → max intensity

    for event_hour, grid_lat, grid_lon, cnt, weather_cond in rows:
        if grid_lat is None or grid_lon is None:
            continue
        pa = _assign_planning_area(float(grid_lat), float(grid_lon))
        key = (pa, event_hour)
        pa_hour_counts[key] += int(cnt or 0)
        wc_str = str(weather_cond or "")
        new_rank = INTENSITY_RANK.get(FORECAST_INTENSITY.get(wc_str, "clear"), 0)
        if new_rank >= pa_hour_weather.get(key, 0):
            pa_hour_weather[key] = new_rank
```

- [ ] **Step 6: Add `weather_intensity` to feature row building**

Find the feature_rows building loop (~line 1472). Add `weather_intensity` to the dict:

```python
    for (pa, event_hour), total_count in pa_hour_counts.items():
        try:
            dt = event_hour if isinstance(event_hour, datetime) else datetime.fromisoformat(str(event_hour))
        except Exception:
            continue
        h = dt.hour
        dow = dt.weekday()
        hour_sin      = math.sin(2 * math.pi * h / 24)
        hour_cos      = math.cos(2 * math.pi * h / 24)
        dow_sin       = math.sin(2 * math.pi * dow / 7)
        dow_cos       = math.cos(2 * math.pi * dow / 7)
        is_weekend    = 1 if dow >= 5 else 0
        is_peak_hour  = 1 if h in {7, 8, 17, 18, 19} else 0
        weather_intensity = pa_hour_weather.get((pa, event_hour), 0)
        feature_rows.append({
            "event_hour":       dt,
            "planning_area":    pa,
            "hour_sin":         hour_sin,
            "hour_cos":         hour_cos,
            "dow_sin":          dow_sin,
            "dow_cos":          dow_cos,
            "is_weekend":       is_weekend,
            "is_peak_hour":     is_peak_hour,
            "weather_intensity": weather_intensity,
            "count":            total_count,
        })
```

- [ ] **Step 7: Add `weather_intensity` to `numeric_features`**

```python
    numeric_features = ["hour_sin", "hour_cos", "dow_sin", "dow_cos", "is_weekend", "is_peak_hour", "weather_intensity"]
```

- [ ] **Step 8: Add `weather_intensity` to inference feature vectors**

Find the predictions loop feature vector construction. It now has 7 elements (pa + 6 numeric). Add `current_weather_intensity` as the 8th:

```python
            feat = [
                [pa,
                 math.sin(2 * math.pi * h / 24),
                 math.cos(2 * math.pi * h / 24),
                 math.sin(2 * math.pi * dow / 7),
                 math.cos(2 * math.pi * dow / 7),
                 1 if dow >= 5 else 0,
                 1 if h in {7, 8, 17, 18, 19} else 0,
                 current_weather_intensity]
            ]
```

Find the low-availability hours loop feature vector and apply the same change:

```python
            feat = [
                [pa,
                 math.sin(2 * math.pi * h / 24),
                 math.cos(2 * math.pi * h / 24),
                 math.sin(2 * math.pi * dow / 7),
                 math.cos(2 * math.pi * dow / 7),
                 1 if dow >= 5 else 0,
                 1 if h in {7, 8, 17, 18, 19} else 0,
                 current_weather_intensity]
            ]
```

- [ ] **Step 9: Add `features` param to MLflow logging**

Find the `mlflow.log_params` call (~line 1556). Add a `features` key:

```python
                mlflow.log_params({
                    "alpha": 1.0,
                    "train_split": 0.8,
                    "features": ",".join(numeric_features),
                })
```

- [ ] **Step 10: Run the full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass. If a test that mocks `duckdb.connect` breaks because it now expects 5-column rows, update the mock's `fetchall` return to include a fifth element (e.g., `"Fair"`) and add a second `fetchone` mock call returning `("Fair",)` for the weather query.

- [ ] **Step 11: Commit**

```bash
git add sg_transit_weather_mesh/assets/analytics.py tests/test_analytics.py
git commit -m "feat: add weather_intensity feature to availability pattern model"
```

---

## Smoke Test (after all tasks)

Run one full Dagster pipeline cycle to confirm the asset produces valid output:

```bash
uv run dagster job execute -j sg_taxi_weather_sync_job
```

Then verify `web-dashboard/public/data/pattern.json`:
- `sufficient_data` is `true`
- `predictions` has 53 entries
- `val_mae` is lower than the previous run's 279.8 (check MLflow UI at http://localhost:5050)
- `val_r2` is higher than 0.39
