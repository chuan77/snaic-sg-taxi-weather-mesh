# SG Taxi & Weather Intelligence Platform

Real-time Singapore taxi fleet tracking and weather demand analytics — Dagster pipeline feeding a live geospatial dashboard with AI/ML insights.

---

## What It Does

The platform ingests live LTA taxi positions (≈ 1,600–2,000 taxis) and NEA 2-hour weather forecasts every 5 minutes via Dagster Software-Defined Assets. Data lands in DuckDB, where analytics assets compute Supply–Demand Index scores, run DBSCAN spatial clustering, and generate weather-triggered surge alerts using a local LLM (Docker Model Runner). Results are exported as JSON files served by a React/TypeScript/Leaflet dark-mode dashboard.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Orchestration | Dagster (Software-Defined Assets) |
| Ingestion | dlt (Data Load Tool) — auto-flattening JSON |
| Warehouse | DuckDB (embedded, single-file) |
| Analytics / ML | Python, NumPy, scikit-learn (DBSCAN, GradientBoostingRegressor) |
| ML Experiment Tracking | MLflow (tracking server + model registry) |
| ML Inference API | FastAPI + Pydantic (uvicorn) |
| Local LLM | Docker Model Runner — `ai/gemma4:E4B` (override via `LLM_BASE_URL` / `LLM_MODEL`) |
| Dashboard | React 18, TypeScript, Vite |
| Map | Leaflet + react-leaflet |
| Styling | Tailwind CSS |

---

## Architecture

```
LTA Taxi API ──┐
                ├─► Dagster (5-min cron)  ─► dlt ─► DuckDB raw schema
NEA Weather API ┘   sg_taxi_weather_sync_job              │
                                                          ▼
                                               analytics_taxi_weather_mart
                                                          │
                                         ┌────────────────┴────────────────┐
                                         ▼                                  ▼
                                  hotspots_export               surge_predictor_export
                                  taxis_export                  taxi_clusters_export
                                  taxi_window_export            subzones_export
                                  weather_nowcast_export
                                         │
                                         ▼
                             web-dashboard/public/data/*.json
                                         │
                             ┌───────────┴───────────────────────┐
                             ▼                                    ▼
                    React hooks (poll every 5 min)     FastAPI (port 8000)
                             │                         ├─► POST /predict/demand
                  ┌──────────┴──────────┐              ├─► GET  /models
                  ▼                    ▼               └─► GET  /experiments/{name}/runs
            Canvas overlays       UI panels
         (TaxiDotLayer,       (DemandHotspots,
          DemandHeatLayer)     StatsPanel, etc.)

Dagster (hourly cron) ─► demand_forecast_export ─► MLflow model registry
demand_forecast_job       (reads warehouse.duckdb;   forecast.json
                           requires prior sync run)
```

---

## AI/ML Features

### Demand Hotspots

Six fixed zones cover Singapore's highest-demand areas. Each zone is a circle of fixed radius centred on a landmark coordinate:

| ID | Zone | Radius |
|---|---|---|
| h1 | Marina Bay / CBD | 1.2 km |
| h2 | Changi Airport | 1.8 km |
| h3 | Orchard Road | 0.9 km |
| h4 | Jurong East | 1.0 km |
| h5 | Woodlands | 1.0 km |
| h6 | Tampines | 1.0 km |

Every 5-minute Dagster run counts the number of live LTA taxis whose coordinates fall within each zone's radius (flat-earth distance, error < 0.1% across Singapore's 50 km span).

#### Demand Level — High / Medium / Low

Zones are ranked by raw taxi count and split into positional thirds — so the label always reflects *relative* conditions across the 6 zones, not an absolute threshold. With 6 zones this yields exactly 2 High, 2 Medium, 2 Low per run. The split shifts whenever the distribution changes (e.g. Orchard spikes on a rainy Friday night).

#### Supply–Demand Index (SDI)

Per-zone score: `SDI = taxi_count / expected_demand`

Expected demand is computed from three multipliers:

```
expected = base_demand × weather_multiplier × rush_hour_factor
```

| Factor | Values |
|---|---|
| **Base demand** (taxis) | h1: 80 · h2: 60 · h3: 70 · h4: 40 · h5: 30 · h6: 50 |
| **Weather multiplier** | clear: 1.0 · drizzle: 1.3 · moderate: 1.7 · heavy: 2.2 · storm: 3.0 |
| **Rush-hour factor** | 1.5 during hours 07, 08, 17, 18, 19 SGT; 1.0 otherwise |

SDI labels:
- **Adequate** — SDI ≥ 1.0 (supply meets or exceeds expected demand)
- **Tight** — 0.5 ≤ SDI < 1.0 (supply below demand, some wait likely)
- **Shortage** — SDI < 0.5 (significant undersupply)

Example: Marina Bay / CBD at 08:00 during heavy rain → expected = 80 × 2.2 × 1.5 = 264 taxis. If 180 taxis are counted, SDI = 180 / 264 ≈ 0.68 → **Tight**.

### Weather-Triggered Surge Predictor
Reads NEA forecasts per hotspot zone, maps intensity to surge scores (0–100), and generates a 1-sentence dispatch alert via Docker Model Runner. Degrades gracefully to template fallback when LLM is unavailable.

### DBSCAN Spatial Clustering
Runs `sklearn.cluster.DBSCAN` (haversine metric, `eps=0.0003` ≈ 1.9 km, `min_samples=10`) on the live taxi snapshot. Clusters are named via LLM or matched against known hotspot zones. Rendered as semi-transparent circles on the map.

### GBR Demand Forecasting
Per-zone GradientBoostingRegressor trained on rolling taxi availability history. Features: last 6 taxi counts (LAG=6). Predicts taxi count 30 minutes ahead (HORIZON=6 × 5-min intervals). One model per hotspot zone is registered in MLflow on an **hourly schedule** (`demand_forecast_job`) — decoupled from the 5-minute sync to prevent registry bloat. Requires ≥ 13 samples per zone; degrades gracefully to no prediction otherwise. Exported to `forecast.json` and displayed as coloured prediction chips (cyan = growing, pink = dropping, amber = stable) on each hotspot row.

### Fleet Coverage Score
Demand-weighted average SDI across all 6 hotspot zones, normalised to a 0–150% scale (capped at 1.5 per zone). Displayed in the Stats Panel as a real-time fleet health indicator with colour coding: red < 50%, amber 50–79%, green ≥ 80%.

### Inverse Supply Heatmap (Supply Gap)
Inverts the taxi density heatmap to highlight areas where supply is lowest relative to surrounding density — a proxy for unmet demand. Toggled per user via the dashboard.

---

## Dashboard Features

- Live taxi point cloud (canvas-rendered, ~1,600+ green dots)
- Demand density heatmap (66×100 grid, box-blurred, 60fps canvas redraw)
- Supply gap / invert mode toggle with context-aware legend
- Heatmap show/hide toggle
- DBSCAN cluster circles (colour-coded by cluster size)
- 2-hour precipitation overlay across NEA forecast areas
- 6-step nowcast weather timeline
- Demand hotspots panel (6 zones with SDI score and surge pulse indicator)
- 30-minute demand prediction chips per hotspot zone (cyan/pink/amber delta colouring)
- Planning areas accordion: top URA planning areas by taxi count with proportional bar chart
- Fleet Coverage Score stat in the stats panel (demand-weighted SDI, red/amber/green)
- Active taxis count and estimated wait time stats panel
- LLM surge alert banner in the header
- **Taxi Cluster tab**: choropleth map of all 332 URA subzones coloured by taxi visit density, count badges at subzone centroids, hover tooltips, top-20 subzone table — based on last 30-minute rolling window of distinct taxi positions

---

## Getting Started

### Option A — Docker Compose (recommended)

All four services (Dagster, MLflow, FastAPI, dashboard) start together. LLM inference runs via Docker Model Runner — no extra setup needed.

**Prerequisites:** Docker Desktop with the Docker Model Runner extension enabled.

```bash
# Set your Data.gov.sg API key
cp .env.example .env
# Edit .env and add: DATA_GOV_API_KEY=your_key_here

docker compose up -d --build
```

| Service | URL |
|---|---|
| Dagster UI | http://localhost:3000 |
| MLflow UI | http://localhost:5050 |
| FastAPI docs | http://localhost:8000/docs |
| Dashboard | http://localhost:5173 |

Click **Materialize All** in the Dagster UI to run the full asset graph. JSON files are written to `web-dashboard/public/data/` and the dashboard auto-refreshes every 5 minutes.

---

### Option B — Local dev

**Prerequisites:**
- Python 3.11+ and `uv` package manager
- Node.js 18+

### 1. Install dependencies

```bash
uv sync
cd web-dashboard && npm install
```

### 2. Configure API key

Edit `config/config.yaml`:

```yaml
api:
  key: "YOUR_DATA_GOV_SG_V2_KEY"
  base_url: "https://data.gov.sg"
orchestration:
  poll_cron_schedule: "*/5 * * * *"          # realtime sync
  forecast_retrain_cron_schedule: "0 * * * *" # GBR retraining (hourly)
```

Get a free API key at [data.gov.sg](https://data.gov.sg).

### 3. Start the pipeline

```bash
uv run dagster dev
```

Open [http://localhost:3000](http://localhost:3000) and click **Materialize All** to run the full asset graph. JSON files will appear in `web-dashboard/public/data/`.

### 4. Start the dashboard

```bash
cd web-dashboard && npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

### 5. (Optional) Enable LLM features

The Docker Compose stack uses Docker Model Runner (`ai/gemma4:E4B`) automatically. For local dev, point `LLM_BASE_URL` to any OpenAI-compatible endpoint — for example LMStudio on port 1234:

```bash
export LLM_BASE_URL=http://localhost:1234/v1
export LLM_MODEL=google/gemma-4-e4b
```

Surge alerts and cluster names are generated by the LLM; all callers degrade gracefully to template fallbacks when the endpoint is unreachable.

### 6. (Optional) Start the MLflow tracking server

```bash
uv run mlflow server \
  --backend-store-uri sqlite:///data/mlflow.db \
  --default-artifact-root ./data/mlruns \
  --host 0.0.0.0 --port 5050 --workers 1
```

Open [http://localhost:5050](http://localhost:5050) to view experiment runs and the model registry. Start this **before** Dagster so experiment tracking is available from the first run.

### 7. (Optional) Start the ML inference API

```bash
uv run uvicorn sg_transit_weather_mesh.api.main:app --port 8000 --reload
```

Requires at least one Dagster pipeline run to register a model in MLflow. Swagger docs available at [http://localhost:8000/docs](http://localhost:8000/docs).

---

## Project Structure

```
snaic-sg-taxi-weather-mesh/
├── config/
│   └── config.yaml                    # API credentials, cron schedules, MLflow config
├── data/
│   ├── warehouse.duckdb               # DuckDB database (gitignored)
│   ├── mlflow.db                      # MLflow backend store (gitignored)
│   └── mlruns/                        # MLflow artifact store (gitignored)
├── scripts/
│   └── migrate_gbr_runs.py            # One-off utility: backfill MLflow run metadata
├── tests/
│   ├── test_hotspots_export.py        # 21 unit tests: zones, _dist_km, taxi counting, ranking
│   ├── test_ingestion.py              # API contract response checks
│   ├── test_api_health.py             # 8 API tests: health, predict/demand, experiments, models
│   ├── test_analytics.py              # Analytics unit tests (SDI, surge, forecast helpers)
│   ├── test_nowcast_export.py         # NEA nowcast logic: mapping, classification, alerts
│   ├── test_dashboard_data.py         # JSON export schema checks for all public/data/ files
│   └── test_dagster_definitions.py    # 10 tests: job selections and schedule cron/timezone
├── sg_transit_weather_mesh/
│   ├── __init__.py                    # Dagster Definitions — two jobs, two schedules
│   ├── utils.py                       # ask_llm(), get_mlflow_config(), configure_mlflow_tracking()
│   ├── resources.py                   # Shared API client
│   ├── api/
│   │   ├── main.py                    # FastAPI app — CORS, lifespan model loading
│   │   ├── schemas.py                 # Pydantic request/response models
│   │   ├── model_store.py             # Thread-safe MLflow model registry loader (singleton)
│   │   └── routes/
│   │       ├── health.py              # GET /health
│   │       ├── models.py              # GET /models
│   │       ├── predict.py             # POST /predict/demand
│   │       └── experiments.py         # GET /experiments/{name}/runs
│   ├── ml/                            # Standalone ML scripts (reserved)
│   ├── notebooks/                     # Exploratory notebooks
│   └── assets/
│       ├── ingestion.py               # dlt pipelines: LTA + NEA → DuckDB raw schema
│       └── analytics.py               # All analytics assets: mart, hotspots, taxis,
│                                      # nowcast, surge predictor, DBSCAN clusters,
│                                      # demand_forecast_export (GBR + MLflow), subzones_export
├── web-dashboard/
│   ├── Dockerfile                     # Production Vite build container
│   ├── public/data/                   # JSON exports (gitignored — generated by Dagster)
│   └── src/
│       ├── App.tsx                    # Root state, all hook calls
│       ├── hooks/                     # useNowcast, useHotspots, useTaxis, useSurge,
│       │                              # useClusters, useForecast, useSubzones, useChatLLM,
│       │                              # useWindowTaxis, useSubzoneCounts
│       ├── components/
│       │   ├── MapLayer.tsx           # Leaflet container, conditional overlay rendering
│       │   ├── TaxiDotLayer.tsx       # Canvas taxi point cloud
│       │   ├── DemandHeatLayer.tsx    # Canvas density / supply-gap heatmap
│       │   ├── ClusterOverlay.tsx     # react-leaflet circles per DBSCAN cluster
│       │   ├── DemandHotspots.tsx     # SDI + surge + 30-min prediction + planning areas
│       │   ├── StatsPanel.tsx         # Active taxis, wait time, Fleet Coverage Score
│       │   ├── HeaderOverlay.tsx      # Alert bar (surge → nowcast priority)
│       │   ├── TaxiClusterPage.tsx    # Subzone choropleth map (30-min window)
│       │   └── Legend.tsx             # Switches: Precipitation / Demand Density / Supply Gap
│       └── types/index.ts             # All shared TypeScript types (incl. SubzoneFeature/Collection)
├── Dockerfile                         # Backend image (python:3.11-slim + curl + uv)
├── docker-compose.yml                 # Full stack: dagster, mlflow, api, frontend
├── CLAUDE.md                          # Developer guide (architecture, patterns, commands)
├── pyproject.toml
└── README.md
```

---

## Running Tests

```bash
uv run pytest tests -v
```

```bash
# TypeScript type check
cd web-dashboard && npx tsc --noEmit
```
