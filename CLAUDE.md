# CLAUDE.md — Developer Guide

## Project Overview

snaic-sg-taxi-weather-mesh is a real-time data platform that ingests live LTA taxi positions and NEA weather forecasts every 5 minutes via Dagster, stores them in DuckDB, runs AI/ML analytics, and serves the results to a React/TypeScript/Leaflet dashboard via static JSON files.

---

## Development Commands

```bash
# Backend pipeline — Dagster UI at http://localhost:3000
uv run dagster dev

# Run all assets once (no UI)
uv run dagster job execute -j sg_taxi_weather_sync_job

# Frontend dashboard — Vite dev server at http://localhost:5173
cd web-dashboard && npm run dev

# MLflow tracking server — UI at http://localhost:5000
# Must be run from the project root directory
# Start before Dagster when you want experiment tracking
uv run mlflow server \
  --backend-store-uri sqlite:///data/mlflow.db \
  --default-artifact-root ./data/mlruns \
  --host 0.0.0.0 --port 5050 --workers 1

# ML API (FastAPI/uvicorn) — Swagger docs at http://localhost:8000/docs
# Must be run from the project root directory
# Start after at least one Dagster pipeline run to load a registered model
uv run uvicorn sg_transit_weather_mesh.api.main:app --port 8000 --reload

# Tests
uv run pytest tests -v

# TypeScript type check (must pass with 0 errors)
cd web-dashboard && npx tsc --noEmit

# Docker Compose — run the full stack in containers
docker compose up -d --build     # build and start all services
docker compose logs -f dagster   # tail Dagster logs
docker compose down              # stop all services
```

Service ports:

| Service | Port |
|---|---|
| Dagster UI | 3000 |
| Vite dev server | 5173 |
| MLflow tracking server | 5050 |
| FastAPI / uvicorn | 8000 |
| Docker Model Runner (LLM) | 12434 |

---

## Architecture

Three-layer system: Dagster writes JSON files consumed by both React and the FastAPI ML API.

```
LTA API ──┐
           ├─► Dagster assets ─► DuckDB (warehouse.duckdb)
NEA API ──┘         │                    │
                     └─► JSON exports    └─► MLflow (demand_forecast models)
                              │                        │
                    web-dashboard/public/data/    FastAPI (port 8000)
                              │                  /predict/demand
                     React hooks (5-min poll)    /models  /health
                              │
                     Components / Canvas overlays
```

### Backend (`sg_transit_weather_mesh/`)

| File | Role |
|---|---|
| `__init__.py` | Dagster `Definitions` — registers all assets + job |
| `assets/ingestion.py` | dlt pipelines: `ingest_sg_raw_data` (LTA + NEA → DuckDB raw schema) |
| `assets/analytics.py` | All analytics assets: mart, hotspots, taxis, nowcast, surge, clusters, `demand_forecast_export` (GBR + MLflow), `subzones_export` |
| `utils.py` | `ask_llm()`, `get_mlflow_config()`, `configure_mlflow_tracking()` |
| `resources.py` | Shared API client |
| `api/main.py` | FastAPI app — CORS, lifespan model loading, route registration |
| `api/schemas.py` | Pydantic schemas: `ZoneForecastItem`, `DemandPredictRequest/Response`, `ModelVersionInfo`, `ExperimentRunItem` |
| `api/model_store.py` | `ModelStore` singleton — thread-safe MLflow model registry loader |
| `api/routes/` | `health.py` (GET /health), `models.py` (GET /models), `predict.py` (POST /predict/demand), `experiments.py` (GET /experiments/{name}/runs) |

### Frontend (`web-dashboard/src/`)

| Path | Role |
|---|---|
| `App.tsx` | Root state (activeTab, invertHeatmap, showHeatmap), all hook calls |
| `hooks/use*.ts` | Data fetching hooks — each polls its JSON file every 5 min (useNowcast, useHotspots, useTaxis, useSurge, useClusters, useForecast, useSubzones) |
| `components/MapLayer.tsx` | Leaflet MapContainer, conditionally renders overlays |
| `components/TaxiDotLayer.tsx` | Canvas taxi point cloud (z-index 450) |
| `components/DemandHeatLayer.tsx` | Canvas density / supply-gap heatmap (z-index 440) |
| `components/ClusterOverlay.tsx` | react-leaflet Circle per DBSCAN cluster |
| `components/DemandHotspots.tsx` | SDI + surge indicator + 30-min prediction chip + planning areas accordion per hotspot zone |
| `components/StatsPanel.tsx` | Active taxis, estimated wait time, Fleet Coverage Score (demand-weighted SDI) |
| `components/HeaderOverlay.tsx` | Alert bar — surge message takes priority over nowcast |
| `components/Legend.tsx` | Switches between Precipitation / Demand Density / Supply Gap |
| `types/index.ts` | All shared TypeScript types |

---

## Key Architectural Patterns

### DuckDB Concurrency
DuckDB only allows one writer at a time. All export assets (`hotspots_export`, `taxis_export`, etc.) declare `AssetIn("analytics_taxi_weather_mart")` to force sequential execution after the mart write completes. Export assets open with `read_only=True` and close in a `try/finally` block.

### Canvas Overlays
Both `TaxiDotLayer` and `DemandHeatLayer` append a `<canvas>` directly to `map.getContainer()` (not to a Leaflet pane). Leaflet applies CSS transforms to panes during pan animation, which would desync canvas pixel positions. Attaching to the container avoids this; the canvas redraws from scratch on every `move`/`zoom`/`resize` event.

### Heatmap Performance
Density grid accumulation and box blur run once per data update (every 5 min) — these are the expensive steps. Per-frame draw only calls `latLngToContainerPoint` three times (to compute pixel scale for the grid), then fills rectangles using a precomputed 256-entry colormap string array. This makes the 66×100 grid draw fast enough at 60fps.

### DBSCAN Parameters
`eps=0.0003` (≈ 1.9 km), `min_samples=10`, `metric='haversine'`. **The eps value is in radians**, not degrees — haversine DBSCAN in sklearn expects radian input after `np.radians(coords)`. Using degrees (e.g. `eps=0.009`) gives an effective radius of ~57 km and merges all Singapore into one cluster.

### LLM Integration
`ask_llm(system_prompt, user_input)` in `utils.py` POSTs to the Docker Model Runner endpoint (`http://localhost:12434/engines/v1` by default). Override via env vars `LLM_BASE_URL` (endpoint) and `LLM_MODEL` (model name, defaults to `ai/gemma4:E4B`). Returns empty string on any exception — all callers must provide a fallback string. LLM features degrade gracefully when the model runner is unavailable. The function is decorated with `@mlflow.trace(span_type=SpanType.LLM)` so calls are visible in the MLflow UI when tracing is enabled.

In Docker Compose, the `dagster` and `frontend` services declare `models: [llm]` to bind to the Docker-hosted model runner; `LLM_BASE_URL` is set to `http://model-runner.docker.internal/engines/v1`.

### MLflow Observability
`_train_gbr_zone()` in `analytics.py` is decorated with `@mlflow.trace()` (CHAIN span) so each zone's training run appears as a nested span in the MLflow UI. `configure_mlflow_tracking()` in `utils.py` sets the tracking URI from `MLFLOW_TRACKING_URI` env var, falling back to `config.yaml`. `get_mlflow_config()` returns `None` when `mlflow.enabled: false` in config, causing all MLflow calls to skip silently. `taxi_clusters_export` logs DBSCAN metrics (silhouette_score, n_clusters, noise_fraction) on each run.

**Docker healthcheck:** `docker-compose.yml` adds a `healthcheck` to the `mlflow` service (`curl http://localhost:5050/health`) and makes `dagster` wait with `depends_on: condition: service_healthy`. This prevents the race condition where `demand_forecast_export` fires before MLflow is ready, silently dropping the `sg-taxi-demand-forecast` experiment. `Dockerfile` installs `curl` for the probe.

### GBR Demand Forecast
`_train_gbr_zone(zone_id, zone_name, counts, sufficient_data)` in `assets/analytics.py`. Features: last LAG=6 taxi counts. Target: count at HORIZON=6 steps ahead (30 min). Params: `n_estimators=50, max_depth=3, random_state=42`, 80/20 train-test split. Returns `(model, train_data, mae)`. Requires ≥ LAG+HORIZON+1 = 13 samples; falls back to `sufficient_data=False` and skips registry registration for that zone. One model per zone is registered to MLflow under the `demand_forecast` experiment after each Dagster run.

### ModelStore and FastAPI Startup
`ModelStore` in `api/model_store.py` is a module-level singleton. On FastAPI startup (lifespan hook in `api/main.py`), it calls `load(mlflow_cfg)` to fetch registered `demand_forecast` models from MLflow. The `GET /health` endpoint reports `models_loaded` and `mlflow_available`, always returning HTTP 200 with `status: "ok"` or `status: "degraded"` — never 503 — so the dashboard can always health-check. `POST /predict/demand` returns 503 when `ModelStore.ready` is `False`.

---

## JSON Data Contracts

All files live in `web-dashboard/public/data/` and are gitignored — generated by Dagster at runtime.

| File | Key fields |
|---|---|
| `taxis.json` | `{ total: number, taxis: [{lat, lng}] }` |
| `nowcast.json` | `{ areas, timeline, regions, alert, valid_period }` |
| `hotspots.json` | `{ total_taxis_online, fleet_coverage_score?: number \| null, hotspots: [{id, name, taxi_count, level, sdi, sdi_label, lat, lng}] }` |
| `surge.json` | `{ alert_active, alert_message, zones: [{id, name, surge_score, alert_level, intensity}] }` |
| `clusters.json` | `{ cluster_count, clusters: [{id, name, centroid_lat, centroid_lng, count, radius_km}] }` |
| `forecast.json` | `{ generated_at, horizon_minutes: 30, sufficient_data, model_mae, zones: [{id, name, current_count, predicted_count, delta}] }` |
| `subzones.json` | `{ generated_at, total_assigned, unassigned, planning_areas: [{name, region, count}] }` |

---

## Testing

`tests/test_hotspots_export.py` — 21 unit tests covering:
- `HOTSPOT_ZONES` structure and required fields
- `_dist_km` flat-earth distance helper (Marina Bay → Changi ≈ 17 km straight-line)
- `_count_taxis_per_zone` assignment logic
- `_rank_hotspots` ordering

`tests/test_api_health.py` — 8 FastAPI tests covering:
- `GET /health` always returns HTTP 200 (with `status: "ok"` or `"degraded"`)
- `/health` response schema includes `status`, `mlflow_available`, `models_loaded`
- `POST /predict/demand` returns 503 when no model is loaded
- `POST /predict/demand` returns predictions with correct schema when model is injected
- `GET /experiments/{name}` returns 404 for unknown experiment names
- `GET /experiments/{name}` returns 503 when MLflow is disabled
- `GET /models` returns 503 when MLflow is disabled

`tests/test_analytics.py` — analytics unit tests (SDI computation, surge scoring, forecast helpers)

`tests/test_ingestion.py` — API contract response checks against LTA and NEA response shapes

`tests/test_nowcast_export.py` — NEA nowcast logic: area-region mapping, intensity classification, timeline derivation, alert generation

`tests/test_dashboard_data.py` — JSON export schema validation for all seven `public/data/` files
