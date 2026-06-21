# sg_transit_weather_mesh/assets/analytics.py
import json
import math
import duckdb
import numpy as np
from sklearn.cluster import DBSCAN
from datetime import datetime
from pathlib import Path
from dagster import asset, Output, AssetIn
from ..utils import ask_llm

_PROJECT_ROOT   = Path(__file__).parent.parent.parent
_NOWCAST_JSON   = _PROJECT_ROOT / "web-dashboard" / "public" / "data" / "nowcast.json"
_HOTSPOTS_JSON  = _PROJECT_ROOT / "web-dashboard" / "public" / "data" / "hotspots.json"
_TAXIS_JSON     = _PROJECT_ROOT / "web-dashboard" / "public" / "data" / "taxis.json"
_SURGE_JSON     = _PROJECT_ROOT / "web-dashboard" / "public" / "data" / "surge.json"
_CLUSTERS_JSON  = _PROJECT_ROOT / "web-dashboard" / "public" / "data" / "clusters.json"

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
_WEATHER_DEMAND_MULT: dict[str, float] = {
    "clear": 1.0, "drizzle": 1.3, "moderate": 1.7, "heavy": 2.2, "storm": 3.0,
}
_RUSH_HOURS = {7, 8, 17, 18, 19}

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


def _name_cluster(centroid_lat: float, centroid_lng: float, hotspot_zones: list[dict]) -> str:
    """Return a name for a taxi cluster: fixed zone name if nearby, else LLM lookup."""
    for zone in hotspot_zones:
        if _dist_km(centroid_lat, centroid_lng, zone["lat"], zone["lng"]) <= 1.5:
            return zone["name"]
    prompt = f"Singapore coordinates: {centroid_lat:.4f}N, {centroid_lng:.4f}E"
    name = ask_llm(_CLUSTER_SYS, prompt)
    return name if name else f"Zone {centroid_lat:.3f},{centroid_lng:.3f}"


def _fmt_display_time(dt: datetime) -> str:
    h = dt.hour % 12 or 12
    return f"{h}:{dt.minute:02d} {'AM' if dt.hour < 12 else 'PM'}"


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

        intensity = FORECAST_INTENSITY.get(str(forecast), "drizzle")
        region = AREA_REGION.get(str(area), "Central")
        areas.append({
            "name": str(area),
            "region": region,
            "forecast": str(forecast),
            "intensity": intensity,
            "latitude": float(lat) if lat is not None else 0.0,
            "longitude": float(lon) if lon is not None else 0.0,
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
            WHERE timestamp = (SELECT MAX(timestamp) FROM raw.taxi_availability)
        """).fetchall()
        snapshot_ts = conn.execute(
            "SELECT MAX(timestamp) FROM raw.taxi_availability"
        ).fetchone()[0]
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
        hotspot_list.append({
            "id":         z["id"],
            "name":       z["name"],
            "level":      z["level"],
            "taxi_count": z["taxi_count"],
            "sdi":        sdi,
            "sdi_label":  sdi_label,
            "lat":        z["lat"],
            "lng":        z["lng"],
        })

    payload = {
        "updated_at":         datetime.now().astimezone().isoformat(),
        "total_taxis_online": len(taxi_rows),
        "snapshot_timestamp": str(snapshot_ts) if snapshot_ts else "",
        "hotspots":           hotspot_list,
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
            WHERE timestamp = (SELECT MAX(timestamp) FROM raw.taxi_availability)
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
            WHERE timestamp = (SELECT MAX(timestamp) FROM raw.taxi_availability)
        """).fetchall()
        snapshot_ts = conn.execute(
            "SELECT MAX(timestamp) FROM raw.taxi_availability"
        ).fetchone()[0]
    finally:
        conn.close()

    coords = np.array(
        [[float(r[0]), float(r[1])] for r in rows if r[0] and r[1]], dtype=np.float64
    )

    clusters: list[dict] = []
    if len(coords) >= 20:
        # eps is in radians for haversine metric: 2 km / 6371 km ≈ 0.000314
        db = DBSCAN(eps=0.0003, min_samples=10, algorithm="ball_tree", metric="haversine").fit(
            np.radians(coords)
        )
        for label in sorted(set(db.labels_)):
            if label == -1:
                continue
            mask     = db.labels_ == label
            pts      = coords[mask]
            centroid = pts.mean(axis=0)
            radius   = max(
                (_dist_km(p[0], p[1], float(centroid[0]), float(centroid[1])) for p in pts),
                default=0.0,
            )
            name = _name_cluster(float(centroid[0]), float(centroid[1]), HOTSPOT_ZONES)
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
        "updated_at":       datetime.now().astimezone().isoformat(),
        "snapshot_timestamp": str(snapshot_ts) if snapshot_ts else "",
        "cluster_count":    len(clusters),
        "clusters":         clusters,
    }
    _CLUSTERS_JSON.parent.mkdir(parents=True, exist_ok=True)
    _CLUSTERS_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    return Output(
        value=None,
        metadata={"cluster_count": len(clusters), "clusters_path": str(_CLUSTERS_JSON)},
    )
