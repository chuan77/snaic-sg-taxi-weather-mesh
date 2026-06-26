# sg_transit_weather_mesh/assets/analytics.py
import json
import json as _json
import math
import duckdb
import numpy as np
from shapely.geometry import shape, Point
from shapely.strtree import STRtree
from sklearn.cluster import DBSCAN
from sklearn.metrics import silhouette_score, mean_absolute_error, mean_squared_error, r2_score
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from datetime import datetime, timedelta
from pathlib import Path
import mlflow
import mlflow.sklearn
from mlflow.entities import SpanType
from dagster import asset, Output, AssetIn, AssetExecutionContext, get_dagster_logger
from ..utils import ask_llm, get_mlflow_config, configure_mlflow_tracking

_PROJECT_ROOT   = Path(__file__).parent.parent.parent
_NOWCAST_JSON   = _PROJECT_ROOT / "web-dashboard" / "public" / "data" / "nowcast.json"
_HOTSPOTS_JSON  = _PROJECT_ROOT / "web-dashboard" / "public" / "data" / "hotspots.json"
_TAXIS_JSON     = _PROJECT_ROOT / "web-dashboard" / "public" / "data" / "taxis.json"
_SURGE_JSON     = _PROJECT_ROOT / "web-dashboard" / "public" / "data" / "surge.json"
_CLUSTERS_JSON    = _PROJECT_ROOT / "web-dashboard" / "public" / "data" / "clusters.json"
_FORECAST24H_JSON   = _PROJECT_ROOT / "web-dashboard" / "public" / "data" / "forecast24h.json"
_FORECAST_JSON      = _PROJECT_ROOT / "web-dashboard" / "public" / "data" / "forecast.json"
_CHAT_CONTEXT_JSON  = _PROJECT_ROOT / "web-dashboard" / "public" / "data" / "chat_context.json"
_PATTERN_JSON       = _PROJECT_ROOT / "web-dashboard" / "public" / "data" / "pattern.json"
_SUBZONES_JSON      = _PROJECT_ROOT / "web-dashboard" / "public" / "data" / "subzones.json"
_TAXIS_WINDOW_15_JSON = _PROJECT_ROOT / "web-dashboard" / "public" / "data" / "taxis_window_15.json"
_TAXIS_WINDOW_30_JSON = _PROJECT_ROOT / "web-dashboard" / "public" / "data" / "taxis_window_30.json"

_CHAMPION_GAP_THRESHOLD = 20  # taxis; guardrail for train_val_mae_gap before champion promotion

# NEA official forecast string → WeatherIntensity level used by the frontend
FORECAST_INTENSITY: dict[str, str] = {
    "Fair":                                    "clear",
    "Fair (Day)":                              "clear",
    "Fair (Night)":                            "clear",
    "Fair & Warm":                             "clear",
    "Partly Cloudy":                           "clear",
    "Partly Cloudy (Day)":                     "clear",
    "Partly Cloudy (Night)":                   "clear",
    "Slightly Hazy":                           "clear",
    "Hazy":                                    "drizzle",
    "Mist":                                    "drizzle",
    "Cloudy":                                  "drizzle",
    "Overcast":                                "drizzle",
    "Passing Showers":                         "drizzle",
    "Light Rain":                              "drizzle",
    "Light Showers":                           "drizzle",
    "Drizzle":                                 "drizzle",
    "Showers":                                 "moderate",
    "Moderate Rain":                           "moderate",
    "Windy, Showers":                          "moderate",
    "Windy, Rain":                             "moderate",
    "Heavy Showers":                           "heavy",
    "Heavy Rain":                              "heavy",
    "Thundery Showers":                        "storm",
    "Heavy Thundery Showers":                  "storm",
    "Heavy Thundery Showers with Gusty Winds": "storm",
}

# All 47 NEA forecast areas → Singapore planning region
AREA_REGION: dict[str, str] = {
    "Ang Mo Kio":              "North",
    "Bedok":                   "East",
    "Bishan":                  "Central",
    "Boon Lay":                "West",
    "Bukit Batok":             "West",
    "Bukit Merah":             "South",
    "Bukit Panjang":           "West",
    "Bukit Timah":             "West",
    "Central Water Catchment": "North",
    "Changi":                  "East",
    "Choa Chu Kang":           "West",
    "City":                    "South",
    "Clementi":                "West",
    "Geylang":                 "East",
    "Hougang":                 "North",
    "Jalan Bahar":             "West",
    "Jurong East":             "West",
    "Jurong Island":           "West",
    "Jurong West":             "West",
    "Kallang":                 "Central",
    "Lim Chu Kang":            "North",
    "Mandai":                  "North",
    "Marine Parade":           "East",
    "Novena":                  "Central",
    "Pasir Ris":               "East",
    "Paya Lebar":              "East",
    "Pioneer":                 "West",
    "Pulau Tekong":            "East",
    "Pulau Ubin":              "East",
    "Punggol":                 "North",
    "Queenstown":              "South",
    "Seletar":                 "North",
    "Sembawang":               "North",
    "Sengkang":                "North",
    "Sentosa":                 "South",
    "Serangoon":               "Central",
    "Southern Islands":        "South",
    "Sungei Kadut":            "North",
    "Tampines":                "East",
    "Tanglin":                 "South",
    "Tengah":                  "West",
    "Toa Payoh":               "Central",
    "Tuas":                    "West",
    "Western Islands":         "West",
    "Western Water Catchment": "West",
    "Woodlands":               "North",
    "Yishun":                  "North",
}

INTENSITY_RANK = {"clear": 0, "drizzle": 1, "moderate": 2, "heavy": 3, "storm": 4}
_RANK_TO_LEVEL = {v: k for k, v in INTENSITY_RANK.items()}
_ALL_REGIONS = ("North", "South", "East", "West", "Central")

# Human-readable condition name shown on the NEA Nowcast timeline dashlet
INTENSITY_LABEL: dict[str, str] = {
    "clear":    "Fair",
    "drizzle":  "Drizzle",
    "moderate": "Showers",
    "heavy":    "Heavy Rain",
    "storm":    "Thunderstorm",
}

# Major demand centres with their geographic catchment radius
HOTSPOT_ZONES: list[dict] = [
    {"id": "h1", "name": "Marina Bay / CBD", "lat": 1.2897, "lng": 103.8501, "radius_km": 1.2},
    {"id": "h2", "name": "Changi Airport",   "lat": 1.3592, "lng": 103.9894, "radius_km": 1.8},
    {"id": "h3", "name": "Orchard Road",     "lat": 1.3048, "lng": 103.8318, "radius_km": 0.9},
    {"id": "h4", "name": "Jurong East",      "lat": 1.3330, "lng": 103.7436, "radius_km": 1.0},
    {"id": "h5", "name": "Woodlands",        "lat": 1.4382, "lng": 103.7891, "radius_km": 1.0},
    {"id": "h6", "name": "Tampines",         "lat": 1.3530, "lng": 103.9434, "radius_km": 1.0},
]


# ── SDI (Supply-Demand Index) calibration constants ──────────────────────────
_ZONE_BASE_DEMAND: dict[str, float] = {
    "h1": 80.0,  # Marina Bay / CBD
    "h2": 60.0,  # Changi Airport
    "h3": 70.0,  # Orchard Road
    "h4": 40.0,  # Jurong East
    "h5": 30.0,  # Woodlands
    "h6": 50.0,  # Tampines
}
_FORECAST_LAG = 6
_FORECAST_HORIZON = 6

_WEATHER_DEMAND_MULT: dict[str, float] = {
    "clear": 1.0, "drizzle": 1.3, "moderate": 1.7, "heavy": 2.2, "storm": 3.0,
}
_RUSH_HOURS = {7, 8, 17, 18, 19}
_TOTAL_BASE_DEMAND = 330.0   # sum of all 6 _ZONE_BASE_DEMAND values
_SDI_CAP = 1.5               # cap per-zone SDI to prevent one surplus masking shortages

# LLM system prompts
_SURGE_SYS = (
    "You are a Singapore taxi dispatch AI. "
    "Write a single concise demand alert for taxi drivers, max 25 words, no emojis, plain English."
)
_CLUSTER_SYS = (
    "You know Singapore's geography well. "
    "Reply with only the name of the nearest Singapore neighbourhood or landmark to the given coordinates. "
    "2-5 words, no punctuation."
)


def _dist_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Flat-earth distance in km — error <0.1% across Singapore's 50 km span."""
    return math.sqrt(((lat2 - lat1) * 111.0) ** 2 + ((lon2 - lon1) * 111.0) ** 2)


def _count_taxis_per_zone(taxi_rows: list, zones: list[dict]) -> list[dict]:
    """Count available taxis whose coordinates fall within each zone's radius."""
    result = []
    for zone in zones:
        count = sum(
            1
            for lat, lon in taxi_rows
            if lat and lon
            and _dist_km(float(lat), float(lon), zone["lat"], zone["lng"]) <= zone["radius_km"]
        )
        result.append({**zone, "taxi_count": count})
    return result


def _rank_hotspots(zones: list[dict]) -> list[dict]:
    """Assign demand level (high / medium / low) by relative taxi density.

    Zones are sorted by taxi_count and split into positional thirds so the
    distribution always reflects relative conditions rather than absolute numbers.
    With 6 zones this yields exactly 2 high, 2 medium, 2 low.
    """
    n = len(zones)
    if n == 0:
        return zones
    ranked  = sorted(zones, key=lambda z: z["taxi_count"], reverse=True)
    high_n  = max(1, n // 3)
    low_n   = max(1, n // 3)
    mid_n   = n - high_n - low_n
    levels  = (["high"] * high_n) + (["medium"] * mid_n) + (["low"] * low_n)
    level_map = {z["id"]: lvl for z, lvl in zip(ranked, levels)}
    return [{**z, "level": level_map[z["id"]]} for z in zones]


def _compute_sdi(zone_id: str, taxi_count: int, weather_intensity: str, current_hour: int) -> tuple[float, str]:
    """Supply-Demand Index: ratio of available taxis to expected demand."""
    rush = 1.5 if current_hour in _RUSH_HOURS else 1.0
    base = _ZONE_BASE_DEMAND.get(zone_id, 50.0)
    mult = _WEATHER_DEMAND_MULT.get(weather_intensity, 1.0)
    expected = max(base * mult * rush, 1.0)
    sdi = round(taxi_count / expected, 2)
    label = "Shortage" if sdi < 0.5 else "Tight" if sdi < 1.0 else "Adequate"
    return sdi, label


def _compute_zone_surges(weather_rows: list, hotspot_zones: list[dict]) -> list[dict]:
    """For each hotspot zone find the nearest NEA forecast area and compute a surge score."""
    # Build list of (area, forecast, lat, lon, valid_period_start)
    areas = []
    for row in weather_rows:
        area, forecast, lat, lon = row[0], row[1], row[2], row[3]
        vp_start = row[4] if len(row) > 4 else ""
        if lat and lon:
            areas.append((str(area), str(forecast), float(lat), float(lon), str(vp_start)))

    results = []
    for zone in hotspot_zones:
        if not areas:
            nearest_area, nearest_forecast, nearest_vp = "Unknown", "Unknown", ""
        else:
            nearest = min(areas, key=lambda a: _dist_km(zone["lat"], zone["lng"], a[2], a[3]))
            nearest_area, nearest_forecast, _, _, nearest_vp = nearest

        intensity = FORECAST_INTENSITY.get(nearest_forecast, "drizzle")
        surge_score = INTENSITY_RANK.get(intensity, 0) * 25  # 0/25/50/75/100
        alert_level = (
            "critical" if surge_score >= 75
            else "high" if surge_score >= 50
            else "moderate" if surge_score >= 25
            else "low"
        )
        results.append({
            "id":           zone["id"],
            "name":         zone["name"],
            "lat":          zone["lat"],
            "lng":          zone["lng"],
            "nearest_area": nearest_area,
            "forecast":     nearest_forecast,
            "intensity":    intensity,
            "surge_score":  surge_score,
            "alert_level":  alert_level,
            "valid_period_start": nearest_vp,
        })
    return results


def _build_surge_alert(zone_surges: list[dict]) -> str:
    """Generate a natural-language alert via LMStudio; falls back to template."""
    top = sorted(zone_surges, key=lambda z: z["surge_score"], reverse=True)[:2]
    if not top or top[0]["surge_score"] == 0:
        return "Mostly fair conditions across Singapore. Normal taxi availability expected."

    zone_summary = "; ".join(
        f"{z['name']} ({z['forecast']}, score {z['surge_score']})" for z in top
    )
    prompt = f"High-demand zones: {zone_summary}. Current time: {datetime.now().strftime('%H:%M')} SGT."
    message = ask_llm(_SURGE_SYS, prompt)
    if message:
        return message

    # Template fallback
    worst = top[0]
    intensity_text = {
        "storm": "Thunderstorms", "heavy": "Heavy rain",
        "moderate": "Showers", "drizzle": "Drizzle", "clear": "Fair weather",
    }.get(worst["intensity"], "Rain")
    return f"{intensity_text} near {worst['name']} — expect surge demand. Position early."


def _load_subzone_shapes(conn) -> tuple:
    """Load MP2019 subzone polygons from DuckDB; build STRtree spatial index.
    Returns (tree, meta_list, geoms_list) — all parallel lists. Returns (None, [], []) on failure.
    """
    try:
        rows = conn.execute("""
            SELECT subzone_name, planning_area, region, geometry_json
            FROM raw.sg_subzone_boundaries
            ORDER BY subzone_code
        """).fetchall()
    except Exception:
        return None, [], []

    meta, geoms = [], []
    for subzone_name, planning_area, region, geom_json in rows:
        try:
            geom = shape(_json.loads(geom_json))
        except Exception:
            continue
        meta.append({
            "subzone":       subzone_name.title(),
            "planning_area": planning_area.title(),
            "region":        region.title(),
        })
        geoms.append(geom)

    if not geoms:
        return None, [], []

    return STRtree(geoms), meta, geoms


def _subzone_for_point(
    lat: float,
    lng: float,
    tree,
    meta: list[dict],
    geoms: list,
) -> dict:
    """Return subzone metadata for a WGS84 coordinate (Shapely point-in-polygon).
    Falls back to nearest centroid for boundary/coast edge cases.
    Returns {} if spatial data not loaded.
    """
    if tree is None:
        return {}
    pt = Point(lng, lat)  # Shapely: x=lng, y=lat
    for idx in tree.query(pt):
        if geoms[idx].contains(pt):
            return meta[idx]
    # Nearest centroid fallback
    min_d = float("inf")
    nearest: dict = {}
    for i, geom in enumerate(geoms):
        d = pt.distance(geom.centroid)
        if d < min_d:
            min_d = d
            nearest = meta[i]
    return nearest


def _name_cluster(
    centroid_lat: float,
    centroid_lng: float,
    hotspot_zones: list[dict],
    sz_tree=None,
    sz_meta: list | None = None,
    sz_geoms: list | None = None,
) -> str:
    """Return a name for a taxi cluster: fixed zone → subzone lookup → LLM fallback."""
    for zone in hotspot_zones:
        if _dist_km(centroid_lat, centroid_lng, zone["lat"], zone["lng"]) <= 1.5:
            return zone["name"]
    if sz_tree is not None:
        result = _subzone_for_point(centroid_lat, centroid_lng, sz_tree, sz_meta or [], sz_geoms or [])
        if result.get("planning_area"):
            return result["planning_area"]
    prompt = f"Singapore coordinates: {centroid_lat:.4f}N, {centroid_lng:.4f}E"
    name = ask_llm(_CLUSTER_SYS, prompt)
    return name if name else f"Zone {centroid_lat:.3f},{centroid_lng:.3f}"


# eps values in haversine radians: 1/6371 per km → range covers ~1.0–3.2 km
_EPS_CANDIDATES = [0.00016, 0.0002, 0.0003, 0.0004, 0.0005]


def _best_dbscan(
    coords_rad: np.ndarray, min_samples: int = 10
) -> tuple[np.ndarray | None, int, float | None]:
    """
    Sweep eps candidates and return (labels, n_clusters, silhouette_score) for the
    run that produces ≥2 valid clusters with the highest silhouette score.
    Falls back to the run with the most clusters (even if < 2) when no eps qualifies.
    Returns (None, 0, None) if coords_rad is empty.
    """
    if len(coords_rad) == 0:
        return None, 0, None

    best_labels: np.ndarray | None = None
    best_score = -2.0
    best_n = 0
    fallback_labels: np.ndarray | None = None
    fallback_n = 0

    for eps in _EPS_CANDIDATES:
        labels = DBSCAN(
            eps=eps, min_samples=min_samples,
            algorithm="ball_tree", metric="haversine",
        ).fit_predict(coords_rad)

        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)

        if n_clusters < 2:
            if n_clusters > fallback_n:
                fallback_labels = labels
                fallback_n = n_clusters
            continue

        mask = labels != -1
        if mask.sum() < 2:
            continue
        score = float(silhouette_score(coords_rad[mask], labels[mask], metric="haversine"))

        if score > best_score:
            best_score = score
            best_labels = labels
            best_n = n_clusters

    if best_labels is not None:
        return best_labels, best_n, best_score
    return fallback_labels, fallback_n, None


def _fmt_display_time(dt: datetime) -> str:
    h = dt.hour % 12 or 12
    return f"{h}:{dt.minute:02d} {'AM' if dt.hour < 12 else 'PM'}"


def _make_cluster_run_name(fetched_at) -> str:
    """Return a deterministic MLflow run name from the mart's max fetched_at."""
    if fetched_at is None:
        return "dbscan_unknown"
    # Normalise to a compact timestamp string regardless of input type
    ts = str(fetched_at).replace(" ", "T").replace(":", "").replace("-", "")[:15]
    return f"dbscan_{ts}"


def _make_forecast_run_name(fetched_at) -> str:
    """Return a deterministic MLflow run name from the mart's max fetched_at."""
    if fetched_at is None:
        return "gbr_unknown"
    ts = str(fetched_at).replace(" ", "T").replace(":", "").replace("-", "")[:15]
    return f"gbr_{ts}"


def _get_champion_val_mae(client, model_name: str) -> float | None:
    """Return the val_mae metric of the run aliased as 'champion' on model_name.

    Returns None if no champion alias exists or metric cannot be fetched.
    """
    try:
        mv = client.get_model_version_by_alias(model_name, "champion")
        history = client.get_metric_history(mv.run_id, "val_mae")
        return history[0].value if history else None
    except Exception:
        return None


def _champion_selection_result(client, model_name: str, version: str, val_mae: float, gap: float):
    """Evaluate whether the new model version should become champion.

    Returns (promoted: bool, tags: dict[str, str]).
    Side-effect: calls client.set_registered_model_alias when promoted=True.
    """
    tags = {}
    if gap > _CHAMPION_GAP_THRESHOLD:
        tags["champion_skipped"] = "guardrail_failed"
        return False, tags

    current_val_mae = _get_champion_val_mae(client, model_name)
    if current_val_mae is not None:
        tags["champion_val_mae"] = str(current_val_mae)

    if current_val_mae is None or val_mae < current_val_mae:
        client.set_registered_model_alias(model_name, "champion", version)
        tags["champion_promoted"] = "true"
        return True, tags

    tags["champion_promoted"] = "false"
    return False, tags


def _classify_areas(rows: list, has_valid_period: bool) -> tuple:
    """Return (classified_areas, vp_start, vp_end, vp_text, update_ts)."""
    areas: list[dict] = []
    vp_start = vp_end = vp_text = update_ts = ""

    for row in rows:
        if has_valid_period:
            area, forecast, lat, lon, ts, vp_s, vp_e, vp_t, upd_ts = row
            if not vp_start:
                vp_start, vp_end, vp_text = str(vp_s), str(vp_e), str(vp_t)
                update_ts = str(upd_ts)
        else:
            area, forecast, lat, lon, ts = row
            if not vp_start:
                vp_start = vp_end = str(ts)
                vp_text = "2-hour forecast"
                update_ts = str(ts)

        if lat is None or lon is None:
            continue
        intensity = FORECAST_INTENSITY.get(str(forecast), "drizzle")
        region = AREA_REGION.get(str(area), "Central")
        areas.append({
            "name": str(area),
            "region": region,
            "forecast": str(forecast),
            "intensity": intensity,
            "latitude": float(lat),
            "longitude": float(lon),
        })

    return areas, vp_start, vp_end, vp_text, update_ts


def _aggregate_regions(classified_areas: list[dict]) -> dict[str, str]:
    """Dominant (highest) intensity per planning region."""
    region_rank: dict[str, int] = {r: 0 for r in _ALL_REGIONS}
    for a in classified_areas:
        r = a["region"]
        rank = INTENSITY_RANK.get(a["intensity"], 0)
        if rank > region_rank.get(r, 0):
            region_rank[r] = rank
    return {r: _RANK_TO_LEVEL[region_rank[r]] for r in _ALL_REGIONS}


def _build_alert(regions: dict[str, str]) -> dict:
    cs_rank = max(INTENSITY_RANK[regions["Central"]], INTENSITY_RANK[regions["South"]])
    max_rank = max(INTENSITY_RANK[v] for v in regions.values())

    if cs_rank >= 4:
        return {
            "active": True,
            "message": "Thunderstorms expected in Central and South Singapore. High demand alert.",
        }
    if cs_rank >= 3:
        return {
            "active": True,
            "message": "Heavy rain in Central and South Singapore. High demand alert.",
        }
    if max_rank >= 4:
        stormy = [r for r, v in regions.items() if INTENSITY_RANK[v] >= 4]
        return {
            "active": True,
            "message": f"Thunderstorms in {' and '.join(stormy)} Singapore. High demand alert.",
        }
    if max_rank >= 2:
        return {"active": False, "message": "Showers across parts of Singapore. Monitor conditions."}
    return {"active": False, "message": "Mostly fair conditions across Singapore."}


def _build_timeline(vp_start: str, vp_end: str, dominant_intensity: str) -> list[dict]:
    label = INTENSITY_LABEL.get(dominant_intensity, dominant_intensity.title())
    try:
        start_dt = datetime.fromisoformat(vp_start)
        end_dt = datetime.fromisoformat(vp_end)
        mid_dt = start_dt + (end_dt - start_dt) / 2
        return [
            {"time": _fmt_display_time(start_dt), "label": label, "intensity": dominant_intensity},
            {"time": _fmt_display_time(mid_dt),   "label": label, "intensity": dominant_intensity},
            {"time": _fmt_display_time(end_dt),   "label": label, "intensity": dominant_intensity},
        ]
    except Exception:
        return [
            {"time": "—", "label": label, "intensity": dominant_intensity},
            {"time": "—", "label": label, "intensity": dominant_intensity},
            {"time": "—", "label": label, "intensity": dominant_intensity},
        ]


@asset(
    ins={"ingest_sg_raw_data": AssetIn()},
    compute_kind="duckdb",
)
def analytics_taxi_weather_mart(ingest_sg_raw_data):
    """Groups geospatial dimensions into coordinate grids inside DuckDB."""
    conn = duckdb.connect(str(_PROJECT_ROOT / "data" / "warehouse.duckdb"))
    try:
        conn.execute("""
            CREATE SCHEMA IF NOT EXISTS mart;
            CREATE OR REPLACE TABLE mart.fct_taxi_weather_trends AS
            SELECT
                DATE_TRUNC('hour', CAST(t.timestamp AS TIMESTAMP)) AS event_hour,
                ROUND(t.latitude,  2) AS grid_lat,
                ROUND(t.longitude, 2) AS grid_lon,
                COUNT(*)             AS available_taxis_count,
                MAX(w.forecast)      AS prominent_weather_condition
            FROM raw.taxi_availability AS t
            LEFT JOIN raw.weather_forecast AS w
              ON DATE_TRUNC('hour', CAST(t.timestamp AS TIMESTAMP))
               = DATE_TRUNC('hour', CAST(w.timestamp AS TIMESTAMP))
             AND ROUND(t.latitude,  1) = ROUND(w.latitude,  1)
             AND ROUND(t.longitude, 1) = ROUND(w.longitude, 1)
            WHERE t.latitude  IS NOT NULL AND t.longitude IS NOT NULL
              AND t.latitude  BETWEEN 1.1 AND 1.5
              AND t.longitude BETWEEN 103.5 AND 104.1
            GROUP BY 1, 2, 3;
        """)
        row_count = conn.execute("SELECT COUNT(*) FROM mart.fct_taxi_weather_trends").fetchone()[0]
    finally:
        conn.close()
    return Output(value=None, metadata={"total_analytics_rows": row_count})


@asset(
    # Depends on analytics_taxi_weather_mart (not just ingest_sg_raw_data) so Dagster
    # always runs this AFTER the write connection is released — prevents DuckDB lock conflicts.
    ins={
        "ingest_sg_raw_data":         AssetIn(),
        "analytics_taxi_weather_mart": AssetIn(),
    },
    compute_kind="duckdb",
)
def weather_nowcast_export(ingest_sg_raw_data, analytics_taxi_weather_mart):
    """Reads latest NEA 2-hr forecast from DuckDB, classifies intensity by area and region,
    generates a dynamic alert message, then writes nowcast.json for the React dashboard."""

    # read_only=True: this asset never writes to DuckDB, only reads from raw.weather_forecast.
    # Opening in read-only mode also allows concurrent readers if needed in future.
    conn = duckdb.connect(str(_PROJECT_ROOT / "data" / "warehouse.duckdb"), read_only=True)

    # v2 schema has valid_period columns; v1 schema does not — try both
    try:
        try:
            rows = conn.execute("""
                SELECT area, forecast, latitude, longitude, timestamp,
                       valid_period_start, valid_period_end, valid_period_text, update_timestamp
                FROM raw.weather_forecast
                WHERE timestamp = (SELECT MAX(timestamp) FROM raw.weather_forecast)
            """).fetchall()
            has_valid_period = True
        except Exception:
            rows = conn.execute("""
                SELECT area, forecast, latitude, longitude, timestamp
                FROM raw.weather_forecast
                WHERE timestamp = (SELECT MAX(timestamp) FROM raw.weather_forecast)
            """).fetchall()
            has_valid_period = False
    finally:
        conn.close()

    if not rows:
        return Output(value=None, metadata={"areas_exported": 0, "alert_active": False})

    classified_areas, vp_start, vp_end, vp_text, update_ts = _classify_areas(rows, has_valid_period)
    regions = _aggregate_regions(classified_areas)
    alert = _build_alert(regions)

    all_ranks = [INTENSITY_RANK.get(a["intensity"], 0) for a in classified_areas]
    dominant_intensity = _RANK_TO_LEVEL[max(all_ranks)]
    timeline = _build_timeline(vp_start, vp_end, dominant_intensity)

    nowcast = {
        "updated_at": update_ts or vp_start,
        "valid_period": {"start": vp_start, "end": vp_end, "text": vp_text},
        "alert": alert,
        "regions": regions,
        "areas": classified_areas,
        "timeline": timeline,
    }

    _NOWCAST_JSON.parent.mkdir(parents=True, exist_ok=True)
    _NOWCAST_JSON.write_text(json.dumps(nowcast, ensure_ascii=False, indent=2))

    return Output(
        value=None,
        metadata={
            "areas_exported": len(classified_areas),
            "alert_active": alert["active"],
            "alert_message": alert["message"],
            "nowcast_path": str(_NOWCAST_JSON),
        },
    )


@asset(
    # Runs after analytics_taxi_weather_mart so the DuckDB write lock is released.
    # Both this asset and weather_nowcast_export use read_only=True and can run in
    # parallel with each other once the write lock is free.
    ins={
        "ingest_sg_raw_data":          AssetIn(),
        "analytics_taxi_weather_mart": AssetIn(),
    },
    compute_kind="duckdb",
)
def hotspots_export(ingest_sg_raw_data, analytics_taxi_weather_mart):
    """Counts available taxis near each major demand centre, ranks zones by relative
    density (high / medium / low), and writes hotspots.json for the React dashboard."""
    conn = duckdb.connect(str(_PROJECT_ROOT / "data" / "warehouse.duckdb"), read_only=True)
    try:
        taxi_rows = conn.execute("""
            SELECT latitude, longitude
            FROM raw.taxi_availability
            WHERE timestamp  = (SELECT MAX(timestamp) FROM raw.taxi_availability)
              AND latitude   IS NOT NULL AND longitude IS NOT NULL
              AND latitude   BETWEEN 1.1 AND 1.5
              AND longitude  BETWEEN 103.5 AND 104.1
        """).fetchall()
        snapshot_ts = conn.execute(
            "SELECT MAX(timestamp) FROM raw.taxi_availability"
        ).fetchone()[0]
        # T2-F3: fetch the two most recent distinct timestamps for competition delta
        ts_rows = conn.execute("""
            SELECT DISTINCT CAST(timestamp AS VARCHAR) AS ts
            FROM raw.taxi_availability ORDER BY ts DESC LIMIT 2
        """).fetchall()
        prev_ts = ts_rows[1][0] if len(ts_rows) >= 2 else None
        prev_counts: dict[str, int] = {}
        if prev_ts is not None:
            prev_taxi_rows = conn.execute("""
                SELECT latitude, longitude
                FROM raw.taxi_availability
                WHERE CAST(timestamp AS VARCHAR) = ?
                  AND latitude  IS NOT NULL AND longitude IS NOT NULL
                  AND latitude  BETWEEN 1.1 AND 1.5
                  AND longitude BETWEEN 103.5 AND 104.1
            """, [prev_ts]).fetchall()
            prev_zones = _count_taxis_per_zone(prev_taxi_rows, HOTSPOT_ZONES)
            prev_counts = {z["id"]: z["taxi_count"] for z in prev_zones}
        # Fetch latest weather for SDI computation
        weather_rows = conn.execute("""
            SELECT area, forecast, latitude, longitude
            FROM raw.weather_forecast
            WHERE timestamp = (SELECT MAX(timestamp) FROM raw.weather_forecast)
        """).fetchall()
    finally:
        conn.close()

    # Build area → intensity lookup for SDI
    area_intensity: dict[str, str] = {}
    for row in weather_rows:
        area_intensity[str(row[0])] = FORECAST_INTENSITY.get(str(row[1]), "drizzle")

    zones_counted = _count_taxis_per_zone(taxi_rows, HOTSPOT_ZONES)
    zones_ranked  = _rank_hotspots(zones_counted)

    current_hour = datetime.now().hour

    def _nearest_intensity(zone: dict) -> str:
        if not weather_rows:
            return "clear"
        nearest = min(
            weather_rows,
            key=lambda r: _dist_km(zone["lat"], zone["lng"], float(r[2] or 0), float(r[3] or 0))
            if r[2] and r[3] else float("inf"),
        )
        return FORECAST_INTENSITY.get(str(nearest[1]), "drizzle")

    hotspot_list = []
    for z in zones_ranked:
        intensity = _nearest_intensity(z)
        sdi, sdi_label = _compute_sdi(z["id"], z["taxi_count"], intensity, current_hour)
        delta_count = (
            z["taxi_count"] - prev_counts[z["id"]]
            if prev_counts and z["id"] in prev_counts
            else None
        )
        hotspot_list.append({
            "id":          z["id"],
            "name":        z["name"],
            "level":       z["level"],
            "taxi_count":  z["taxi_count"],
            "delta_count": delta_count,
            "sdi":         sdi,
            "sdi_label":   sdi_label,
            "lat":         z["lat"],
            "lng":         z["lng"],
        })

    # T2-F7: Fleet Coverage Score — demand-weighted average of capped per-zone SDIs
    coverage_score: float | None = None
    if hotspot_list:
        coverage_score = round(
            sum(
                min(h["sdi"], _SDI_CAP) * _ZONE_BASE_DEMAND.get(h["id"], 0.0)
                / _TOTAL_BASE_DEMAND
                for h in hotspot_list
            ),
            3,
        )

    payload = {
        "updated_at":           datetime.now().astimezone().isoformat(),
        "total_taxis_online":   len(taxi_rows),
        "snapshot_timestamp":   str(snapshot_ts) if snapshot_ts else "",
        "fleet_coverage_score": coverage_score,
        "hotspots":             hotspot_list,
    }

    _HOTSPOTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    _HOTSPOTS_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    return Output(
        value=None,
        metadata={
            "total_taxis":    len(taxi_rows),
            "zone_counts":    {z["name"]: z["taxi_count"] for z in zones_ranked},
            "hotspots_path":  str(_HOTSPOTS_JSON),
        },
    )


@asset(
    ins={
        "ingest_sg_raw_data":          AssetIn(),
        "analytics_taxi_weather_mart": AssetIn(),
    },
    compute_kind="duckdb",
)
def taxis_export(ingest_sg_raw_data, analytics_taxi_weather_mart):
    """Exports the latest taxi availability snapshot as taxis.json for the React map overlay."""
    conn = duckdb.connect(str(_PROJECT_ROOT / "data" / "warehouse.duckdb"), read_only=True)
    try:
        rows = conn.execute("""
            SELECT latitude, longitude
            FROM raw.taxi_availability
            WHERE timestamp  = (SELECT MAX(timestamp) FROM raw.taxi_availability)
              AND latitude   IS NOT NULL AND longitude IS NOT NULL
              AND latitude   BETWEEN 1.1 AND 1.5
              AND longitude  BETWEEN 103.5 AND 104.1
        """).fetchall()
        snapshot_ts = conn.execute(
            "SELECT MAX(timestamp) FROM raw.taxi_availability"
        ).fetchone()[0]
    finally:
        conn.close()

    taxis = [
        {"lat": round(float(r[0]), 4), "lng": round(float(r[1]), 4)}
        for r in rows if r[0] and r[1]
    ]

    payload = {
        "updated_at":         datetime.now().astimezone().isoformat(),
        "snapshot_timestamp": str(snapshot_ts) if snapshot_ts else "",
        "total":              len(taxis),
        "taxis":              taxis,
    }
    _TAXIS_JSON.parent.mkdir(parents=True, exist_ok=True)
    _TAXIS_JSON.write_text(json.dumps(payload, separators=(",", ":")))

    return Output(value=None, metadata={"taxi_count": len(taxis), "taxis_path": str(_TAXIS_JSON)})


@asset(
    ins={
        "ingest_sg_raw_data":          AssetIn(),
        "analytics_taxi_weather_mart": AssetIn(),
    },
    compute_kind="duckdb",
    group_name="exports",
)
def taxi_window_export(context: AssetExecutionContext, ingest_sg_raw_data, analytics_taxi_weather_mart) -> Output:
    """Exports distinct taxi positions for 15-min and 30-min rolling windows."""
    conn = duckdb.connect(str(_PROJECT_ROOT / "data" / "warehouse.duckdb"), read_only=True)
    try:
        rows_15 = conn.execute("""
            SELECT DISTINCT latitude AS lat, longitude AS lng
            FROM raw.taxi_availability
            WHERE timestamp >= (SELECT MAX(timestamp) - INTERVAL 15 MINUTE FROM raw.taxi_availability)
              AND latitude  IS NOT NULL AND longitude IS NOT NULL
              AND latitude  BETWEEN 1.1 AND 1.5
              AND longitude BETWEEN 103.5 AND 104.1
        """).fetchall()
        rows_30 = conn.execute("""
            SELECT DISTINCT latitude AS lat, longitude AS lng
            FROM raw.taxi_availability
            WHERE timestamp >= (SELECT MAX(timestamp) - INTERVAL 30 MINUTE FROM raw.taxi_availability)
              AND latitude  IS NOT NULL AND longitude IS NOT NULL
              AND latitude  BETWEEN 1.1 AND 1.5
              AND longitude BETWEEN 103.5 AND 104.1
        """).fetchall()
    finally:
        conn.close()

    def _write(rows: list, window: int, path) -> int:
        taxis = [{"lat": round(float(r[0]), 4), "lng": round(float(r[1]), 4)} for r in rows]
        out = {"window_minutes": window, "total": len(taxis), "taxis": taxis}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, separators=(",", ":")))
        return len(taxis)

    count_15 = _write(rows_15, 15, _TAXIS_WINDOW_15_JSON)
    count_30 = _write(rows_30, 30, _TAXIS_WINDOW_30_JSON)

    context.log.info(f"Exported {count_15} positions (15 min) and {count_30} positions (30 min)")
    return Output(
        value=None,
        metadata={
            "taxi_count_15min": count_15,
            "taxi_count_30min": count_30,
            "taxis_window_15_path": str(_TAXIS_WINDOW_15_JSON),
            "taxis_window_30_path": str(_TAXIS_WINDOW_30_JSON),
        },
    )


@asset(
    ins={
        "ingest_sg_raw_data":          AssetIn(),
        "analytics_taxi_weather_mart": AssetIn(),
    },
    compute_kind="python",
)
def surge_predictor_export(ingest_sg_raw_data, analytics_taxi_weather_mart):
    """Scores each hotspot zone for demand surge risk using the NEA 2-hr forecast,
    then calls the local LLM to generate a natural-language alert message."""
    conn = duckdb.connect(str(_PROJECT_ROOT / "data" / "warehouse.duckdb"), read_only=True)
    try:
        weather_rows = conn.execute("""
            SELECT area, forecast, latitude, longitude, valid_period_start
            FROM raw.weather_forecast
            WHERE timestamp = (SELECT MAX(timestamp) FROM raw.weather_forecast)
        """).fetchall()
    finally:
        conn.close()

    zone_surges   = _compute_zone_surges(weather_rows, HOTSPOT_ZONES)
    alert_message = _build_surge_alert(zone_surges)
    alert_active  = any(z["surge_score"] >= 50 for z in zone_surges)

    payload = {
        "updated_at":    datetime.now().astimezone().isoformat(),
        "alert_active":  alert_active,
        "alert_message": alert_message,
        "zones":         zone_surges,
    }
    _SURGE_JSON.parent.mkdir(parents=True, exist_ok=True)
    _SURGE_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    return Output(
        value=None,
        metadata={
            "alert_active":  alert_active,
            "alert_message": alert_message,
            "zone_scores":   {z["name"]: z["surge_score"] for z in zone_surges},
        },
    )


@asset(
    ins={
        "ingest_sg_raw_data":          AssetIn(),
        "analytics_taxi_weather_mart": AssetIn(),
    },
    compute_kind="python",
)
def taxi_clusters_export(ingest_sg_raw_data, analytics_taxi_weather_mart):
    """Discovers dynamic taxi supply clusters with DBSCAN and names them via LLM."""
    conn = duckdb.connect(str(_PROJECT_ROOT / "data" / "warehouse.duckdb"), read_only=True)
    try:
        rows = conn.execute("""
            SELECT latitude, longitude
            FROM raw.taxi_availability
            WHERE timestamp  = (SELECT MAX(timestamp) FROM raw.taxi_availability)
              AND latitude   IS NOT NULL AND longitude IS NOT NULL
              AND latitude   BETWEEN 1.1 AND 1.5
              AND longitude  BETWEEN 103.5 AND 104.1
        """).fetchall()
        snapshot_ts = conn.execute(
            "SELECT MAX(timestamp) FROM raw.taxi_availability"
        ).fetchone()[0]
        _data_ts = snapshot_ts
    finally:
        conn.close()

    conn_sz = duckdb.connect(str(_PROJECT_ROOT / "data" / "warehouse.duckdb"), read_only=True)
    try:
        sz_tree, sz_meta, sz_geoms = _load_subzone_shapes(conn_sz)
    finally:
        conn_sz.close()

    coords = np.array(
        [[float(r[0]), float(r[1])] for r in rows if r[0] and r[1]], dtype=np.float64
    )

    clusters: list[dict] = []
    sil_score: float | None = None
    if len(coords) >= 20:
        coords_rad = np.radians(coords)
        labels, _n_clusters, sil_score = _best_dbscan(coords_rad)

        # ── MLflow experiment tracking ─────────────────────────────────────────
        _mlflow_cfg = get_mlflow_config()
        if _mlflow_cfg is not None and sil_score is not None:
            try:
                import mlflow
                configure_mlflow_tracking(_mlflow_cfg)
                mlflow.set_experiment(_mlflow_cfg["experiments"]["taxi_clusters"])
                _run_name = _make_cluster_run_name(_data_ts)
                _existing = mlflow.search_runs(
                    experiment_names=[_mlflow_cfg["experiments"]["taxi_clusters"]],
                    filter_string=f"tags.mlflow.runName = '{_run_name}'",
                    max_results=1,
                )
                if not _existing.empty:
                    _log.info(f"MLflow run '{_run_name}' already exists — skipping duplicate logging")
                else:
                    with mlflow.start_run(run_name=_run_name):
                        mlflow.log_params({
                            "min_samples": 10, "metric": "haversine",
                            "algorithm": "ball_tree", "coord_count": len(coords),
                        })
                        mlflow.log_metric("silhouette_score", round(sil_score, 4))
                        mlflow.log_metric("n_clusters", _n_clusters)
                        if labels is not None:
                            mlflow.log_metric("noise_fraction",
                                round(float((labels == -1).sum()) / len(labels), 4))
                        mlflow.set_tag("pipeline", "taxi_clusters_export")
            except Exception:
                pass

        if labels is not None:
            for label in sorted(set(labels)):
                if label == -1:
                    continue
                mask     = labels == label
                pts      = coords[mask]
                centroid = pts.mean(axis=0)
                radius   = max(
                    (_dist_km(p[0], p[1], float(centroid[0]), float(centroid[1])) for p in pts),
                    default=0.0,
                )
                name = _name_cluster(
                    float(centroid[0]), float(centroid[1]), HOTSPOT_ZONES,
                    sz_tree, sz_meta, sz_geoms,
                )
                clusters.append({
                    "id":           f"c{label}",
                    "name":         name,
                    "centroid_lat": round(float(centroid[0]), 4),
                    "centroid_lng": round(float(centroid[1]), 4),
                    "count":        int(mask.sum()),
                    "radius_km":    round(radius, 2),
                })
            clusters.sort(key=lambda c: c["count"], reverse=True)

    payload = {
        "updated_at":         datetime.now().astimezone().isoformat(),
        "snapshot_timestamp": str(snapshot_ts) if snapshot_ts else "",
        "cluster_count":      len(clusters),
        "silhouette_score":   round(sil_score, 4) if sil_score is not None else None,
        "clusters":           clusters,
    }
    _CLUSTERS_JSON.parent.mkdir(parents=True, exist_ok=True)
    _CLUSTERS_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    return Output(
        value=None,
        metadata={
            "cluster_count":    len(clusters),
            "silhouette_score": sil_score if sil_score is not None else "n/a",
            "clusters_path":    str(_CLUSTERS_JSON),
        },
    )


@asset(
    ins={
        "ingest_sg_raw_data":          AssetIn(),
        "analytics_taxi_weather_mart": AssetIn(),
    },
    compute_kind="duckdb",
)
def weather_24hr_export(ingest_sg_raw_data, analytics_taxi_weather_mart):
    """Reads latest NEA 24-hour forecast from DuckDB, computes dominant intensity per
    time period and per region, then writes forecast24h.json for the React dashboard."""
    conn = duckdb.connect(str(_PROJECT_ROOT / "data" / "warehouse.duckdb"), read_only=True)
    try:
        try:
            rows = conn.execute("""
                SELECT period_text, period_start, period_end,
                       region, forecast,
                       general_forecast, temp_low, temp_high, rh_low, rh_high,
                       valid_start, valid_end, fetched_at
                FROM raw.weather_forecast_24hr
                WHERE fetched_at = (SELECT MAX(fetched_at) FROM raw.weather_forecast_24hr)
                ORDER BY period_start, region
            """).fetchall()
        except Exception:
            rows = []
    finally:
        conn.close()

    if not rows:
        return Output(value=None, metadata={"periods_exported": 0})

    # Extract scalar header fields from any row (identical across all rows for same fetched_at)
    r0 = rows[0]
    general_forecast = str(r0[5])
    temp_low, temp_high = int(r0[6] or 0), int(r0[7] or 0)
    rh_low, rh_high   = int(r0[8] or 0), int(r0[9] or 0)
    valid_start, valid_end = str(r0[10] or ""), str(r0[11] or "")
    updated_at = str(r0[12] or datetime.now().astimezone().isoformat())

    general_intensity = FORECAST_INTENSITY.get(general_forecast, "drizzle")

    # Group rows by period_text (preserving period_start order from SQL ORDER BY)
    from collections import OrderedDict
    periods_map: OrderedDict = OrderedDict()
    for row in rows:
        period_text  = str(row[0])
        period_start = str(row[1] or "")
        period_end   = str(row[2] or "")
        region       = str(row[3])
        forecast     = str(row[4] or "")
        intensity    = FORECAST_INTENSITY.get(forecast, "drizzle")

        if period_text not in periods_map:
            periods_map[period_text] = {
                "time_text":  period_text,
                "start":      period_start,
                "end":        period_end,
                "regions":    {},
                "_ranks":     [],
                "_forecasts": [],
            }
        periods_map[period_text]["regions"][region] = intensity
        periods_map[period_text]["_ranks"].append(INTENSITY_RANK.get(intensity, 0))
        periods_map[period_text]["_forecasts"].append(forecast)

    periods: list[dict] = []
    for p in periods_map.values():
        max_rank = max(p["_ranks"]) if p["_ranks"] else 0
        # dominant_forecast: pick the forecast string that matches the highest intensity rank
        dominant_intensity = _RANK_TO_LEVEL[max_rank]
        dominant_forecast = next(
            (f for f, r in zip(p["_forecasts"], p["_ranks"]) if r == max_rank),
            general_forecast,
        )
        if not dominant_forecast:
            dominant_forecast = dominant_intensity.replace("_", " ").title()
        periods.append({
            "time_text":          p["time_text"],
            "start":              p["start"],
            "end":                p["end"],
            "dominant_intensity": dominant_intensity,
            "dominant_forecast":  dominant_forecast,
            "regions":            p["regions"],
        })

    payload = {
        "updated_at":   updated_at,
        "valid_period": {"start": valid_start, "end": valid_end},
        "general": {
            "forecast":   general_forecast,
            "intensity":  general_intensity,
            "temp_low":   temp_low,
            "temp_high":  temp_high,
            "rh_low":     rh_low,
            "rh_high":    rh_high,
        },
        "periods": periods,
    }

    _FORECAST24H_JSON.parent.mkdir(parents=True, exist_ok=True)
    _FORECAST24H_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    return Output(
        value=None,
        metadata={
            "periods_exported":  len(periods),
            "general_intensity": general_intensity,
            "forecast24h_path":  str(_FORECAST24H_JSON),
        },
    )


@mlflow.trace(name="train_gbr_zone", span_type=SpanType.CHAIN)
def _train_gbr_zone(
    zone_id: str,
    zone_name: str,
    counts: list,
    sufficient_data: bool,
) -> dict:
    """Train GBR for one hotspot zone. Traced as a CHAIN span per zone per pipeline run.

    Returns a dict with:
        zone_out  – the forecast entry for zones_out
        model     – fitted GradientBoostingRegressor (or None when data is insufficient)
        X_train   – training feature matrix (or None)
        mae       – holdout MAE (or None)
    """
    current_count = counts[-1] if counts else 0
    _fallback = {
        "zone_out": {
            "id": zone_id, "name": zone_name,
            "current_count": current_count, "predicted_count": current_count, "delta": 0,
        },
        "model": None, "X_train": None, "mae": None,
    }

    if not sufficient_data or len(counts) < _FORECAST_LAG + _FORECAST_HORIZON + 1:
        return _fallback

    X_rows, y_rows = [], []
    for i in range(_FORECAST_LAG, len(counts) - _FORECAST_HORIZON):
        X_rows.append([counts[i - k] for k in range(1, _FORECAST_LAG + 1)])
        y_rows.append(counts[i + _FORECAST_HORIZON])

    if len(X_rows) < 5:
        return _fallback

    X = np.array(X_rows, dtype=float)
    y = np.array(y_rows, dtype=float)
    split = max(1, int(len(X) * 0.8))

    model = GradientBoostingRegressor(n_estimators=50, max_depth=3, random_state=42)
    model.fit(X[:split], y[:split])

    mae: float | None = None
    if len(X[split:]) > 0:
        mae = float(np.mean(np.abs(model.predict(X[split:]) - y[split:])))

    latest = np.array([[counts[-k] for k in range(1, _FORECAST_LAG + 1)]], dtype=float)
    predicted_count = max(0, int(round(float(model.predict(latest)[0]))))

    return {
        "zone_out": {
            "id": zone_id, "name": zone_name,
            "current_count": current_count,
            "predicted_count": predicted_count,
            "delta": predicted_count - current_count,
        },
        "model": model,
        "X_train": X[:split],
        "mae": mae,
    }


@asset(
    compute_kind="python",
)
def demand_forecast_export():
    """Trains a GradientBoostingRegressor per hotspot zone on rolling snapshot history,
    predicts taxi count 30 minutes ahead, writes forecast.json."""

    # ── MLflow tracing entry-point: resolve experiment object before DuckDB queries ──
    # experiment_id is passed explicitly to start_run() to avoid a race with
    # taxi_clusters_export (also runs in parallel) which calls set_experiment() for its
    # own experiment and overwrites the process-global active-experiment state.
    _log = get_dagster_logger()
    _mlflow_cfg = get_mlflow_config()
    _experiment = None
    if _mlflow_cfg is not None:
        try:
            configure_mlflow_tracking(_mlflow_cfg)
            _experiment = mlflow.set_experiment(_mlflow_cfg["experiments"]["demand_forecast"])
        except Exception as e:
            _log.warning(f"MLflow setup failed — skipping experiment tracking: {e}")

    conn = duckdb.connect(str(_PROJECT_ROOT / "data" / "warehouse.duckdb"), read_only=True)
    try:
        ts_rows = conn.execute("""
            SELECT DISTINCT CAST(timestamp AS VARCHAR) AS ts
            FROM raw.taxi_availability
            ORDER BY ts
        """).fetchall()
        timestamps = [r[0] for r in ts_rows]

        zone_counts: dict[str, list[int]] = {z["id"]: [] for z in HOTSPOT_ZONES}
        for z in HOTSPOT_ZONES:
            lat_d = z["radius_km"] / 111.0
            lng_d = z["radius_km"] / (111.0 * math.cos(math.radians(z["lat"])))
            rows = conn.execute("""
                SELECT CAST(timestamp AS VARCHAR) AS ts, COUNT(*) AS cnt
                FROM raw.taxi_availability
                WHERE latitude   IS NOT NULL AND longitude IS NOT NULL
                  AND latitude   BETWEEN ? AND ?
                  AND longitude  BETWEEN ? AND ?
                GROUP BY ts
                ORDER BY ts
            """, [
                z["lat"] - lat_d, z["lat"] + lat_d,
                z["lng"] - lng_d, z["lng"] + lng_d,
            ]).fetchall()
            count_map = {r[0]: int(r[1]) for r in rows}
            zone_counts[z["id"]] = [count_map.get(ts, 0) for ts in timestamps]
        _data_ts = None
        try:
            _data_ts = conn.execute(
                "SELECT MAX(event_hour) FROM mart.fct_taxi_weather_trends"
            ).fetchone()[0]
        except Exception:
            pass
    finally:
        conn.close()

    sufficient_data = len(timestamps) >= 13
    generated_at = datetime.now().astimezone().isoformat()
    zones_out: list = []
    all_maes: list[float] = []
    _last_model = None
    _last_zone_X = None
    model_mae: float | None = None

    # ── MLflow experiment run: open start_run BEFORE @mlflow.trace() calls fire ──
    # @mlflow.trace() on _train_gbr_zone must nest inside an active run; calling it
    # outside start_run creates an orphaned trace context that causes the subsequent
    # run to exit as FAILED even when all work succeeds.
    # experiment_id is passed explicitly so a parallel DBSCAN set_experiment() call
    # cannot override the global active experiment between Block 1 and here.
    if _experiment is not None:
        try:
            _run_name = _make_forecast_run_name(_data_ts)
            _existing = mlflow.search_runs(
                experiment_ids=[_experiment.experiment_id],
                filter_string=f"tags.mlflow.runName = '{_run_name}'",
                max_results=1,
            )
            if not _existing.empty:
                _log.info(f"MLflow run '{_run_name}' already exists — skipping duplicate logging")
                with mlflow.start_run(
                    run_name=f"{_run_name}_retrain",
                    experiment_id=_experiment.experiment_id,
                    tags={"skip_logging": "true"},
                ):
                    for z in HOTSPOT_ZONES:
                        result = _train_gbr_zone(z["id"], z["name"], zone_counts[z["id"]], sufficient_data)
                        zones_out.append(result["zone_out"])
                        if result["model"] is not None:
                            _last_model = result["model"]
                            _last_zone_X = result["X_train"]
                        if result["mae"] is not None:
                            all_maes.append(result["mae"])
                model_mae = float(np.mean(all_maes)) if all_maes else None
            else:
                with mlflow.start_run(
                    run_name=_run_name,
                    experiment_id=_experiment.experiment_id,
                ):
                    mlflow.log_params({
                        "n_estimators": 50, "max_depth": 3, "random_state": 42,
                        "lag": _FORECAST_LAG, "horizon": _FORECAST_HORIZON, "train_split": 0.8,
                    })
                    for z in HOTSPOT_ZONES:
                        result = _train_gbr_zone(z["id"], z["name"], zone_counts[z["id"]], sufficient_data)
                        zones_out.append(result["zone_out"])
                        if result["model"] is not None:
                            _last_model = result["model"]
                            _last_zone_X = result["X_train"]
                        if result["mae"] is not None:
                            all_maes.append(result["mae"])
                    model_mae = float(np.mean(all_maes)) if all_maes else None
                    if model_mae is not None:
                        mlflow.log_metric("mean_mae_across_zones", model_mae)
                    mlflow.log_metric("zones_with_data", len(all_maes))
                    mlflow.set_tag("sufficient_data", str(sufficient_data))
                    mlflow.set_tag("pipeline", "demand_forecast_export")
                    if _last_model is not None and _last_zone_X is not None:
                        try:
                            mlflow.sklearn.log_model(
                                sk_model=_last_model,
                                artifact_path="model",
                                registered_model_name=_mlflow_cfg["registry"]["demand_forecast"],
                                input_example=_last_zone_X[-1:],
                            )
                        except Exception:
                            pass
        except Exception as e:
            _log.warning(f"MLflow run failed to complete: {e}")
    else:
        # MLflow disabled or setup failed — train without tracking
        for z in HOTSPOT_ZONES:
            result = _train_gbr_zone(z["id"], z["name"], zone_counts[z["id"]], sufficient_data)
            zones_out.append(result["zone_out"])
            if result["model"] is not None:
                _last_model = result["model"]
                _last_zone_X = result["X_train"]
            if result["mae"] is not None:
                all_maes.append(result["mae"])
        model_mae = float(np.mean(all_maes)) if all_maes else None

    payload = {
        "generated_at":    generated_at,
        "horizon_minutes": 30,
        "sufficient_data": sufficient_data,
        "model_mae":       model_mae,
        "zones":           zones_out,
    }

    _FORECAST_JSON.parent.mkdir(parents=True, exist_ok=True)
    _FORECAST_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    return Output(
        value=None,
        metadata={
            "zones_exported":  len(zones_out),
            "sufficient_data": sufficient_data,
            "model_mae":       model_mae,
            "forecast_path":   str(_FORECAST_JSON),
        },
    )


@asset(
    compute_kind="python",
)
def availability_pattern_export():
    """Trains a Ridge regression model on historical taxi availability per planning area,
    predicts availability at now/+30min/+60min/+120min, and writes pattern.json."""
    _log = get_dagster_logger()
    generated_at = datetime.now().astimezone().isoformat()

    conn = duckdb.connect(str(_PROJECT_ROOT / "data" / "warehouse.duckdb"), read_only=True)
    try:
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
        try:
            sz_rows = conn.execute("""
                SELECT planning_area, geometry_json FROM raw.sg_subzone_boundaries
            """).fetchall()
        except Exception:
            sz_rows = []
    finally:
        conn.close()

    _wc = (weather_row[0] or "") if weather_row else ""
    current_weather_intensity = INTENSITY_RANK.get(FORECAST_INTENSITY.get(_wc, "clear"), 0)

    # Build STRtree for planning area assignment
    area_shapes: list[tuple] = []  # (area_name, shape)
    for pa_name, geom_json in sz_rows:
        try:
            geom = shape(_json.loads(geom_json))
            area_shapes.append((pa_name.title(), geom))
        except Exception:
            continue

    if area_shapes:
        _pa_geoms = [g for _, g in area_shapes]
        _pa_names = [n for n, _ in area_shapes]
        _pa_tree = STRtree(_pa_geoms)
    else:
        _pa_tree = None
        _pa_geoms = []
        _pa_names = []

    def _assign_planning_area(lat: float, lng: float) -> str:
        if _pa_tree is None:
            return "Unknown"
        pt = Point(lng, lat)
        for idx in _pa_tree.query(pt):
            if _pa_geoms[idx].contains(pt):
                return _pa_names[idx]
        # nearest centroid fallback
        min_d = float("inf")
        nearest = "Unknown"
        for i, g in enumerate(_pa_geoms):
            d = pt.distance(g.centroid)
            if d < min_d:
                min_d = d
                nearest = _pa_names[i]
        return nearest

    # Aggregate: assign planning area and group by (planning_area, event_hour)
    from collections import defaultdict
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

    # Collect distinct event_hours
    all_hours = sorted({eh for (_, eh) in pa_hour_counts.keys()})

    if len(all_hours) < 48:
        _PATTERN_JSON.parent.mkdir(parents=True, exist_ok=True)
        _PATTERN_JSON.write_text(json.dumps({"sufficient_data": False, "generated_at": generated_at}, indent=2))
        return Output(value=None, metadata={"sufficient_data": False, "event_hours": len(all_hours)})

    # Build feature rows
    feature_rows = []
    for (pa, event_hour), total_count in pa_hour_counts.items():
        try:
            dt = event_hour if isinstance(event_hour, datetime) else datetime.fromisoformat(str(event_hour))
        except Exception:
            continue
        h = dt.hour
        dow = dt.weekday()
        hour_sin = math.sin(2 * math.pi * h / 24)
        hour_cos = math.cos(2 * math.pi * h / 24)
        dow_sin  = math.sin(2 * math.pi * dow / 7)
        dow_cos  = math.cos(2 * math.pi * dow / 7)
        is_weekend = 1 if dow >= 5 else 0
        is_peak_hour = 1 if h in {7, 8, 17, 18, 19} else 0
        weather_intensity = pa_hour_weather.get((pa, event_hour), 0)
        feature_rows.append({
            "event_hour": dt,
            "planning_area": pa,
            "hour_sin": hour_sin,
            "hour_cos": hour_cos,
            "dow_sin":  dow_sin,
            "dow_cos":  dow_cos,
            "is_weekend": is_weekend,
            "is_peak_hour": is_peak_hour,
            "weather_intensity": weather_intensity,
            "count": total_count,
        })

    # Temporal split 80/20
    feature_rows.sort(key=lambda r: r["event_hour"])
    split_idx = max(1, int(len(feature_rows) * 0.8))
    train_rows = feature_rows[:split_idx]
    val_rows   = feature_rows[split_idx:]

    numeric_features = ["hour_sin", "hour_cos", "dow_sin", "dow_cos", "is_weekend", "is_peak_hour", "weather_intensity"]
    categorical_features = ["planning_area"]

    def _to_X_y(rows_list):
        X_cat  = [[r["planning_area"]] for r in rows_list]
        X_num  = [[r[f] for f in numeric_features] for r in rows_list]
        y      = [r["count"] for r in rows_list]
        return X_cat, X_num, y

    _, _, y_tr = _to_X_y(train_rows)
    _, _, y_va = _to_X_y(val_rows)

    # Build full feature matrix: categorical + numeric
    X_train_full = [[r["planning_area"]] + [r[f] for f in numeric_features] for r in train_rows]
    X_val_full   = [[r["planning_area"]] + [r[f] for f in numeric_features] for r in val_rows]

    preprocessor = ColumnTransformer(transformers=[
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), [0]),
        ("num", "passthrough", list(range(1, 1 + len(numeric_features)))),
    ])

    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("ridge", Ridge(alpha=1.0)),
    ])

    pipeline.fit(X_train_full, y_tr)
    y_pred_tr = pipeline.predict(X_train_full)
    y_pred_va = pipeline.predict(X_val_full)

    train_mae = float(mean_absolute_error(y_tr, y_pred_tr))
    val_mae   = float(mean_absolute_error(y_va, y_pred_va))
    val_rmse  = float(mean_squared_error(y_va, y_pred_va) ** 0.5)
    val_r2    = float(r2_score(y_va, y_pred_va)) if len(y_va) > 1 else 0.0
    train_val_mae_gap = val_mae - train_mae

    # Per-area val MAE
    area_val_mae: dict[str, float] = {}
    area_rows_map: dict[str, list] = defaultdict(list)
    for i, r in enumerate(val_rows):
        area_rows_map[r["planning_area"]].append(i)
    for pa, idxs in area_rows_map.items():
        y_true_pa = [y_va[i] for i in idxs]
        y_pred_pa = [y_pred_va[i] for i in idxs]
        area_val_mae[pa] = float(mean_absolute_error(y_true_pa, y_pred_pa))

    all_areas = sorted({r["planning_area"] for r in feature_rows})

    # MLflow logging
    _mlflow_cfg = get_mlflow_config()
    if _mlflow_cfg is not None:
        try:
            configure_mlflow_tracking(_mlflow_cfg)
            mlflow.set_experiment(_mlflow_cfg["experiments"]["availability_pattern"])
            with mlflow.start_run(run_name=f"ridge_{datetime.now().strftime('%Y%m%dT%H%M')}"):
                mlflow.log_params({"alpha": 1.0, "train_split": 0.8, "features": ",".join(numeric_features)})
                mlflow.log_metric("train_mae", train_mae)
                mlflow.log_metric("val_mae", val_mae)
                mlflow.log_metric("val_rmse", val_rmse)
                mlflow.log_metric("val_r2", val_r2)
                mlflow.log_metric("train_val_mae_gap", train_val_mae_gap)
                mlflow.log_metric("n_training_rows", len(train_rows))
                mlflow.log_metric("n_planning_areas", len(all_areas))
                for pa, mae_val in area_val_mae.items():
                    key = "area_mae_" + pa.lower().replace(" ", "_")
                    mlflow.log_metric(key, mae_val)
                model_info = mlflow.sklearn.log_model(
                    sk_model=pipeline,
                    artifact_path="model",
                    registered_model_name=_mlflow_cfg["registry"]["availability_pattern"],
                )
                _client = mlflow.MlflowClient()
                _model_name = _mlflow_cfg["registry"]["availability_pattern"]
                _version = model_info.registered_model_version
                if _version is not None:
                    _, _tags = _champion_selection_result(
                        _client, _model_name, str(_version), val_mae, train_val_mae_gap
                    )
                    for _tag_key, _tag_val in _tags.items():
                        mlflow.set_tag(_tag_key, _tag_val)
        except Exception as exc:
            _log.warning(f"MLflow logging for availability_pattern_export failed: {exc}", exc_info=True)

    # Generate predictions per area for now / +30min / +60min / +120min
    now_dt = datetime.now()
    offsets = {"now": timedelta(0), "in_30min": timedelta(minutes=30),
               "in_1h": timedelta(hours=1), "in_2h": timedelta(hours=2)}

    predictions = []
    for pa in all_areas:
        pred_row = {}
        for label, delta in offsets.items():
            target_dt = now_dt + delta
            h = target_dt.hour
            dow = target_dt.weekday()
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
            pred_val = max(0, int(round(float(pipeline.predict(feat)[0]))))
            pred_row[label] = pred_val
        predictions.append({"area": pa, **pred_row})

    # Low-availability hours: 24 predictions per area, mark hours < 50% of daily peak
    low_availability_hours: dict[str, list[int]] = {}
    for pa in all_areas:
        hourly_preds = []
        for h in range(24):
            dow = now_dt.weekday()
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
            hourly_preds.append(max(0, float(pipeline.predict(feat)[0])))
        daily_peak = max(hourly_preds) if hourly_preds else 1.0
        threshold = daily_peak * 0.5
        low_hours = [h for h, p in enumerate(hourly_preds) if p < threshold]
        if low_hours:
            low_availability_hours[pa] = low_hours

    payload = {
        "generated_at": generated_at,
        "sufficient_data": True,
        "val_mae": round(val_mae, 4),
        "val_r2": round(val_r2, 4),
        "train_val_mae_gap": round(train_val_mae_gap, 4),
        "predictions": predictions,
        "low_availability_hours": low_availability_hours,
    }

    _PATTERN_JSON.parent.mkdir(parents=True, exist_ok=True)
    _PATTERN_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    return Output(
        value=None,
        metadata={
            "sufficient_data": True,
            "event_hours": len(all_hours),
            "planning_areas": len(all_areas),
            "val_mae": round(val_mae, 4),
            "val_r2": round(val_r2, 4),
            "pattern_path": str(_PATTERN_JSON),
        },
    )


@asset(
    ins={
        "weather_nowcast_export": AssetIn(),
        "hotspots_export":        AssetIn(),
        "weather_24hr_export":    AssetIn(),
        "subzones_export":        AssetIn(),
    },
    compute_kind="python",
)
def chat_context_export(
    weather_nowcast_export,
    hotspots_export,
    weather_24hr_export,
    subzones_export,
):
    """Merges nowcast, hotspot, 30-min forecast, and 24-hr data into a single LLM context file."""

    def _read_json(path: Path) -> dict:
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}

    nowcast  = _read_json(_NOWCAST_JSON)
    hotspots = _read_json(_HOTSPOTS_JSON)
    forecast = _read_json(_FORECAST_JSON)
    f24      = _read_json(_FORECAST24H_JSON)
    subzones = _read_json(_SUBZONES_JSON)
    pattern  = _read_json(_PATTERN_JSON)

    forecast_map = {z["id"]: z for z in forecast.get("zones", [])}

    merged_hotspots = []
    for h in hotspots.get("hotspots", []):
        fz = forecast_map.get(h.get("id", ""), {})
        merged_hotspots.append({
            "id":              h.get("id", ""),
            "name":            h.get("name", ""),
            "taxi_count":      h.get("taxi_count", 0),
            "predicted_count": fz.get("predicted_count", h.get("taxi_count", 0)),
            "delta":           fz.get("delta", 0),
            "sdi_label":       h.get("sdi_label", ""),
            "level":           h.get("level", "low"),
        })

    # Top 30 planning areas by count
    planning_areas_sorted = sorted(
        subzones.get("planning_areas", []),
        key=lambda x: x.get("count", 0),
        reverse=True,
    )[:30]

    # Rainfall readings
    rainfall_active = False
    rainfall_stations: list[dict] = []
    try:
        conn_rain = duckdb.connect(str(_PROJECT_ROOT / "data" / "warehouse.duckdb"), read_only=True)
        try:
            rain_rows = conn_rain.execute("""
                SELECT station_name, rainfall_mm, latitude, longitude
                FROM raw.rainfall_readings
                WHERE rainfall_mm > 0
                ORDER BY rainfall_mm DESC
            """).fetchall()
            if rain_rows:
                rainfall_active = True
                rainfall_stations = [
                    {"name": str(r[0]), "rainfall_mm": round(float(r[1]), 1), "lat": r[2], "lng": r[3]}
                    for r in rain_rows
                ]
        except Exception:
            pass
        finally:
            conn_rain.close()
    except Exception:
        pass

    payload = {
        "generated_at":               datetime.now().astimezone().isoformat(),
        "total_taxis":                hotspots.get("total_taxis_online", 0),
        "valid_period_text":          nowcast.get("valid_period", {}).get("text", ""),
        "sufficient_forecast":        forecast.get("sufficient_data", False),
        "areas":                      nowcast.get("areas", []),
        "hotspots":                   merged_hotspots,
        "nowcast_timeline":           nowcast.get("timeline", []),
        "forecast_24h":               f24.get("periods", []),
        "planning_areas":             planning_areas_sorted,
        "rainfall_active":            rainfall_active,
        "rainfall_stations":          rainfall_stations,
        "planning_area_predictions":  pattern.get("predictions", []),
        "low_availability_hours":     pattern.get("low_availability_hours", {}),
    }

    _CHAT_CONTEXT_JSON.parent.mkdir(parents=True, exist_ok=True)
    _CHAT_CONTEXT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    return Output(
        value=None,
        metadata={
            "areas_count":       len(payload["areas"]),
            "hotspots_count":    len(payload["hotspots"]),
            "chat_context_path": str(_CHAT_CONTEXT_JSON),
        },
    )


@asset(
    ins={
        "ingest_sg_raw_data":          AssetIn(),
        "analytics_taxi_weather_mart": AssetIn(),
    },
    compute_kind="python",
)
def subzones_export(ingest_sg_raw_data, analytics_taxi_weather_mart):
    """Assigns each taxi to a URA planning area via point-in-polygon (MP2019 boundaries),
    counts taxis per area, writes subzones.json."""

    conn = duckdb.connect(str(_PROJECT_ROOT / "data" / "warehouse.duckdb"), read_only=True)
    try:
        taxi_rows = conn.execute("""
            SELECT latitude, longitude
            FROM raw.taxi_availability
            WHERE timestamp  = (SELECT MAX(timestamp) FROM raw.taxi_availability)
              AND latitude   IS NOT NULL AND longitude IS NOT NULL
              AND latitude   BETWEEN 1.1 AND 1.5
              AND longitude  BETWEEN 103.5 AND 104.1
        """).fetchall()
        sz_tree, sz_meta, sz_geoms = _load_subzone_shapes(conn)
    finally:
        conn.close()

    area_counts: dict[str, dict] = {}
    unassigned = 0
    for lat, lng in taxi_rows:
        result = _subzone_for_point(float(lat), float(lng), sz_tree, sz_meta, sz_geoms)
        if not result:
            unassigned += 1
            continue
        key = result["planning_area"]
        if key not in area_counts:
            area_counts[key] = {"name": key, "region": result["region"], "count": 0}
        area_counts[key]["count"] += 1

    planning_areas = sorted(area_counts.values(), key=lambda x: x["count"], reverse=True)

    payload = {
        "generated_at":   datetime.now().astimezone().isoformat(),
        "total_assigned": sum(a["count"] for a in planning_areas),
        "unassigned":     unassigned,
        "planning_areas": planning_areas,
    }

    _SUBZONES_JSON.parent.mkdir(parents=True, exist_ok=True)
    _SUBZONES_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    return Output(
        value=None,
        metadata={
            "planning_areas_with_taxis": len(planning_areas),
            "total_assigned":            payload["total_assigned"],
            "unassigned":                unassigned,
            "subzones_path":             str(_SUBZONES_JSON),
        },
    )
