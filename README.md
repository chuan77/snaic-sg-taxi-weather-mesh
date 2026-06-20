# 🚖 Real-Time Singapore Taxi Fleet & Weather Predictive Pipeline

An enterprise-grade, asset-oriented ELT pipeline built to orchestrate, model, and analyze the interplay between live geospatial transportation volume (LTA API) and real-time precipitation/weather conditions (NEA API).

### 🛠️ Core Technology Stack
* **Orchestration**: Dagster (Software-Defined Assets & Configurable Daemon Chronometers)
* **Ingestion (ELT)**: dlt (Data Load Tool) featuring native JSON schema flattening & type inference
* **Warehouse Engine**: DuckDB (Embedded Vectorized Query Execution)
* **Feature Engineering**: Python/Polars & Geospatial Space Bucketing SQL
* **Environment Control**: YAML Configuration Management Profiles

### 🚀 Key Architectural Strengths
* **Dynamic Cron Tuning**: Polling frequency (5-15 min cycles) is entirely decoupled from the core framework execution code, handled dynamically via profile layers.
* **Geospatial Alignment**: Resolves spatial grain variance by mapping individual taxi coordinates to meteorological zones using customized SQL decimal grid clustering.
* **Resilient Data Contracts**: Upstream API schema modifications are automatically trapped and handled gracefully by dlt's schema evolution component, preventing system downtime.


🗺️ Final Logical Architecture Blueprint
This modern, single-node data lakehouse adheres strictly to an Asset-Oriented ELT Architecture. It decouples orchestration logic, secure config parsing, raw schema ingestion, and analytical transformation.

Architectural Principles & Design Features

1. Software-Defined Assets (SDA) over Task-DAGs: Instead of modeling the system as blind operational tasks (fetch_data \(\rightarrow \) run_sql), the architecture is modeled entirely around Data Assets. This provides deep observability: engineers know exactly what table is out-of-date, rather than which step in a script failed.

2. Schema Evolution and Auto-Flattening: By embedding dlt inside the ingestion layer, the system treats upstream API json payload drift defensively. dlt mutates raw DuckDB variant types and handles nested geospatial structs cleanly without breaking schema boundaries.

3. Decoupled In-Memory Storage-Compute: DuckDB acts as an ultra-fast, local structured file engine (warehouse.duckdb). This bypasses heavy database server overhead during joins, keeping cloud or local storage cheap, isolated, and highly performant.

4. Geospatial Decimal Grid Clustering: To cleanly merge point-source taxi coordinates (exact GPS lat/long) with region-based weather forecasts (station quadrants), the transformation layer implements a Spatial-Bucket Join Matrix using analytical SQL functions to aggregate features smoothly.


📁 Project File Structure Strategy

sg-transit-weather-mesh/
├── .github/
│   └── workflows/
│       └── ci-cd.yaml             # Continuous Integration syntax validation pipeline
├── data/
│   └── warehouse.duckdb           # Core persistent database (Git-ignored in production)
├── tests/
│   ├── __init__.py
│   ├── test_ingestion.py          # Pytest definitions checking API contract responses
│   └── test_analytics.py          # Schema validation tests for transformation steps
├── sg_transit_weather_mesh/
│   ├── __init__.py                # Main Dagster Definitions entry point & deployment manifest
│   ├── utils.py                   # Decoupled safe YAML profile loading functions
│   ├── resources.py               # Shared API client connections and abstract resources
│   ├── assets/
│   │   ├── __init__.py
│   │   ├── ingestion.py           # DLT micro-engines collecting LTA/NEA datasets
│   │   └── analytics.py           # DuckDB SQL matrices performing the grid-bucketing joins
│   └── notebooks/
│       └── exploration.ipynb      # Marimo/Jupyter predictive sandbox environments
├── config.yaml                    # Local configuration profile (API credentials, Cron timers)
├── pyproject.toml                 # Modern Python packaging declaration (UV / Poetry / Pip)
└── README.md                      # Corporate portfolio presentation documentation

🎨 UI/UX Design System & Dashboard Layout StrategyThe user interface balances functional data density with immediate scannability. It implements a grid system featuring responsive micro-dashlets (KPI cards) flanking a central geographic visualization component.

┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        🇸🇬 SG TRANSIT-WEATHER INTERACTIVE MESH                         │
├───────────────────────┬────────────────────────────────────────────────────────────────┤
│       DASHLETS        │                    LIVE GEOSPATIAL HEATMAP                     │
├───────────────────────┤                                                                │
│  TOTAL ACTIVE TAXIS   │                                                                │
│       [ 4,892 ]       │                         ▲ (Woodlands)                          │
│                       │                                                                │
├───────────────────────┤                                                                │
│  AVG RAINFALL INTENS. │             ◄ (Tuas)               ● (CBD) ►                   │
│       [ 12.4mm ]      │                                                                │
│                       │                                  ▼ (Changi)                    │
├───────────────────────┤                                                                │
│ MONSOON ALERT METRIC  │                                                                │
│    [ Heavy Rain ]     │                                                                │
└───────────────────────┴────────────────────────────────────────────────────────────────┘

* Color Palette Theory: Deep slate background (#0f172a) to minimise visual strain, vibrant cyan (#06b6d4) for active transit data, and emerald-to-amber progressions for meteorological fluctuations.

*Reactivity Engine: Marimo's native runtime graph ensures that whenever an API element updates or a slider shifts, only dependent dashboard tokens rerender, eliminating global application flickering.

## 🚀 Getting Started

Ensure you have Python 3.11+ and **`uv`** installed.

### 1. Installation & Environment Construction
Clone the repository and spin up your isolated virtual workspace dependencies instantaneously:
```bash
git clone https://github.com
cd sg-transit-weather-mesh
uv sync
```

### 2. Configure Access Tokens
Create a configuration file at `config/config.yaml`:
```yaml
api:
  key: "YOUR_DATA_GOV_SG_V2_KEY"
  base_url: "https://data.gov.sg"
orchestration:
  poll_cron_schedule: "*/5 * * * *"
```

### 3. Run the Automated Verification Suite
Execute the pytest framework across both the ingestion components and analytics databases:
```bash
uv run pytest tests -v
```

### 4. Trigger Data Pipelines & Dashboard
Launch the **Dagster Orchestrator UI** to manage background API syncing jobs:
```bash
uv run dagster dev
```
Navigate to `http://localhost:3000`, click **Materialize All** to run the ELT graph.

In a secondary terminal window, launch the interactive **Marimo Data Dashboard**:
```bash
uv run marimo run sg_transit_weather_mesh/notebooks/dashboard.py
```

# 🚖 sg-transit-weather-mesh

[![CI Pipeline](https://github.com)](https://github.com)
[![Python Version](https://shields.io)](https://python.org)
[![Package Manager](https://shields.io)](https://github.com)

An enterprise-grade, asset-oriented ELT pipeline built to ingest, transform, orchestrate, and visualize the real-time interaction between live public transit fleet density (LTA Taxi Availability API) and meteorological conditions (NEA Weather Forecast API) across Singapore.

---

## 🗺️ Logical Architecture

The platform operates on a single-node Data Lakehouse pattern executing an Asset-Oriented ELT design.

. Resume Metric Points (.pdf / .docx)

* Built and architected a production-ready real-time data engineering platform using Dagster, dlt, and DuckDB to ingest, clean, and combine live geospatial transportation (LTA) and meteorological (NEA) public API datasets.

* Implemented an asset-oriented pipeline that dynamically reads interval settings from decoupled YAML profiles to automatically poll endpoints every 5 to 15 minutes, ensuring low-latency data updates.

* Eliminated pipeline processing failures due to unexpected payload variations by using dlt’s automated schema discovery and nested JSON flattening rules.

* Resolved spatial grain mismatches between exact point coordinates and region-based weather data by building a customized geospatial decimal grid clustering algorithm inside DuckDB, creating analytics-ready tables for predictive modeling.

3. Professional Portfolio Narrative (Web / Case Study)

TITLE: Building a High-Throughput Live Geospatial Streaming & Ingestion Platform

PROBLEM STATEMENT: Real-time public API streams often suffer from schema drift, high frequency processing overhead, and spatial grain alignment mismatches (e.g., trying to join an instantaneous GPS point location against a broad regional weather polygon).

SOLUTION: I architected a modern, single-node ELT system using Python, Dagster, dlt, and DuckDB. Rather than relying on rigid, legacy task-driven scripts, I leveraged Software-Defined Data Assets. The pipeline extracts real-time taxi and weather vectors securely via API gateways, flattens dense JSON payloads into structured raw storage surfaces using dlt, and runs vectorized SQL conversions inside an embedded DuckDB file engine.

OUTCOME: The final data mart provides clear, clean, and joined features to analytics users and ML models on a consistent schedule. The system is fully configurable via production config YAML profiles and isolates storage, compute, and ingestion logic using clean, modern data engineering principles.

# snaic-sg-taxi-weather-mesh
