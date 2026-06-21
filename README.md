# SG Taxi & Weather Intelligence Platform

Real-time Singapore taxi fleet tracking and weather demand analytics — Dagster pipeline feeding a live geospatial dashboard with AI/ML insights.

---

## What It Does

The platform ingests live LTA taxi positions (≈ 1,600–2,000 taxis) and NEA 2-hour weather forecasts every 5 minutes via Dagster Software-Defined Assets. Data lands in DuckDB, where analytics assets compute Supply–Demand Index scores, run DBSCAN spatial clustering, and generate weather-triggered surge alerts using a local LLM (LMStudio). Results are exported as JSON files served by a React/TypeScript/Leaflet dark-mode dashboard.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Orchestration | Dagster (Software-Defined Assets) |
| Ingestion | dlt (Data Load Tool) — auto-flattening JSON |
| Warehouse | DuckDB (embedded, single-file) |
| Analytics / ML | Python, NumPy, scikit-learn (DBSCAN) |
| Local LLM | LMStudio — `google/gemma-4-e4b` |
| Dashboard | React 18, TypeScript, Vite |
| Map | Leaflet + react-leaflet |
| Styling | Tailwind CSS |

---

## Architecture

```
LTA Taxi API ──┐
                ├─► Dagster (5-min cron) ─► dlt ─► DuckDB raw schema
NEA Weather API ┘                                        │
                                                         ▼
                                              analytics_taxi_weather_mart
                                                         │
                                          ┌──────────────┴──────────────┐
                                          ▼                              ▼
                                   hotspots_export              surge_predictor_export
                                   taxis_export                 taxi_clusters_export
                                   weather_nowcast_export
                                          │
                                          ▼
                              web-dashboard/public/data/*.json
                                          │
                                          ▼
                              React hooks (poll every 5 min)
                                          │
                              ┌───────────┴───────────┐
                              ▼                       ▼
                        Canvas overlays         UI panels
                     (TaxiDotLayer,          (DemandHotspots,
                      DemandHeatLayer)        StatsPanel, etc.)
```

---

## AI/ML Features

### Supply–Demand Index (SDI)
Per-zone score comparing available taxis against expected demand. Expected demand is modelled from zone baseline demand × weather multiplier × rush-hour factor. Labels: Adequate / Tight / Shortage.

### Weather-Triggered Surge Predictor
Reads NEA forecasts per hotspot zone, maps intensity to surge scores (0–100), and generates a 1-sentence dispatch alert via LMStudio. Degrades gracefully to template fallback when LLM is unavailable.

### DBSCAN Spatial Clustering
Runs `sklearn.cluster.DBSCAN` (haversine metric, `eps=0.0003` ≈ 1.9 km, `min_samples=10`) on the live taxi snapshot. Clusters are named via LLM or matched against known hotspot zones. Rendered as semi-transparent circles on the map.

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
- Active taxis count and estimated wait time stats panel
- LLM surge alert banner in the header

---

## Getting Started

### Prerequisites
- Python 3.11+
- `uv` package manager
- Node.js 18+ (for the dashboard)
- (Optional) LMStudio with `google/gemma-4-e4b` loaded for LLM features

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
  poll_cron_schedule: "*/5 * * * *"
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

Start LMStudio, load `google/gemma-4-e4b`, and enable the local inference server on port 1234. Surge alerts and cluster names will then be generated by the LLM rather than using template fallbacks.

---

## Project Structure

```
snaic-sg-taxi-weather-mesh/
├── config/
│   └── config.yaml                    # API credentials and cron schedule
├── data/
│   └── warehouse.duckdb               # DuckDB database (gitignored)
├── tests/
│   ├── test_hotspots_export.py        # 21 unit tests: zones, _dist_km, taxi counting, ranking
│   └── test_ingestion.py              # API contract response checks
├── sg_transit_weather_mesh/
│   ├── __init__.py                    # Dagster Definitions entry point
│   ├── utils.py                       # ask_llm() — LMStudio client with graceful fallback
│   ├── resources.py                   # Shared API client
│   └── assets/
│       ├── ingestion.py               # dlt pipelines: LTA + NEA → DuckDB raw schema
│       └── analytics.py               # All analytics assets: mart, hotspots, taxis,
│                                      # nowcast, surge predictor, DBSCAN clusters
├── web-dashboard/
│   ├── public/data/                   # JSON exports (gitignored — generated by Dagster)
│   └── src/
│       ├── App.tsx                    # Root state, all hook calls
│       ├── hooks/                     # useNowcast, useHotspots, useTaxis, useSurge, useClusters
│       ├── components/
│       │   ├── MapLayer.tsx           # Leaflet container, conditional overlay rendering
│       │   ├── TaxiDotLayer.tsx       # Canvas taxi point cloud
│       │   ├── DemandHeatLayer.tsx    # Canvas density / supply-gap heatmap
│       │   ├── ClusterOverlay.tsx     # react-leaflet circles per DBSCAN cluster
│       │   ├── DemandHotspots.tsx     # SDI + surge indicators per zone
│       │   ├── HeaderOverlay.tsx      # Alert bar (surge → nowcast priority)
│       │   └── Legend.tsx             # Switches: Precipitation / Demand Density / Supply Gap
│       └── types/index.ts             # All shared TypeScript types
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
