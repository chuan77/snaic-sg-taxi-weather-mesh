# sg_transit_weather_mesh/notebooks/dashboard_data.py
"""
Pure-Python data layer for the Operations Dashboard.
Decoupled from the marimo UI layer so it can be unit-tested independently.
"""
from __future__ import annotations

import datetime

import numpy as np
import pandas as pd

ALL_REGIONS: list[str] = ["North", "South", "East", "West", "Central"]
ALL_PIPELINES: list[str] = ["ingest_sg_raw_data", "analytics_mart", "data_quality", "api_sync"]

# Approximate geographic centroids for each planning region (lat, lon)
REGION_COORDS: dict[str, tuple[float, float]] = {
    "North":   (1.4390, 103.8360),   # Woodlands / Yishun corridor
    "South":   (1.2710, 103.8198),   # Harbourfront / Sentosa
    "East":    (1.3521, 103.9450),   # Tampines / Changi
    "West":    (1.3406, 103.6955),   # Jurong Island corridor
    "Central": (1.3000, 103.8400),   # Orchard / Toa Payoh
}

_SLA_BASELINES: dict[str, float] = {
    "ingest_sg_raw_data": 0.92,
    "analytics_mart": 0.88,
    "data_quality": 0.95,
    "api_sync": 0.78,
}
_REGION_USER_BASELINES: dict[str, int] = {
    "North": 3200, "South": 4100, "East": 2800, "West": 3600, "Central": 5200,
}

DEFAULT_START = datetime.date(2026, 5, 22)
DEFAULT_END = datetime.date(2026, 6, 21)


def generate_de_data(seed: int = 42) -> pd.DataFrame:
    """Generate deterministic DE health mock data (30 days × 4 pipelines × 5 regions = 600 rows).

    Columns: date, pipeline, region, sla_met, volume_gb, error_count,
             run_duration_min, freshness_hours
    """
    rng = np.random.default_rng(seed=seed)
    dates = pd.date_range(DEFAULT_START, DEFAULT_END, freq="D")
    rows = []
    for date in dates:
        is_weekend = date.dayofweek >= 5
        for pipeline in ALL_PIPELINES:
            for region in ALL_REGIONS:
                prob = _SLA_BASELINES[pipeline] * (0.82 if is_weekend else 1.0)
                sla_met = bool(rng.random() < prob)
                rows.append({
                    "date": date,
                    "pipeline": pipeline,
                    "region": region,
                    "sla_met": sla_met,
                    "volume_gb": round(
                        float(rng.uniform(0.5, 15.0) * (0.6 if is_weekend else 1.0)), 2
                    ),
                    "error_count": int(rng.poisson(1.5 if sla_met else 9.0)),
                    "run_duration_min": round(float(rng.uniform(2.0, 45.0)), 1),
                    "freshness_hours": round(
                        float(rng.uniform(0.3, 3.0) if sla_met else rng.uniform(5.0, 24.0)), 1
                    ),
                })
    return pd.DataFrame(rows)


def generate_biz_data(seed: int = 42) -> pd.DataFrame:
    """Generate deterministic Business Analytics mock data (30 days × 5 regions = 150 rows).

    Columns: date, region, active_users, session_count, conversions, revenue, conversion_rate
    """
    rng = np.random.default_rng(seed=seed)
    dates = pd.date_range(DEFAULT_START, DEFAULT_END, freq="D")
    rows = []
    for i, date in enumerate(dates):
        for region in ALL_REGIONS:
            trend = i * float(rng.uniform(8, 25))
            users = max(0, int(_REGION_USER_BASELINES[region] + trend + float(rng.normal(0, 80))))
            sessions = int(users * float(rng.uniform(1.5, 2.5)))
            conversions = int(sessions * float(rng.uniform(0.04, 0.11)))
            revenue = round(conversions * float(rng.uniform(20, 90)), 2)
            rows.append({
                "date": date,
                "region": region,
                "active_users": users,
                "session_count": sessions,
                "conversions": conversions,
                "revenue": revenue,
                "conversion_rate": round(conversions / sessions * 100, 2) if sessions > 0 else 0.0,
            })
    return pd.DataFrame(rows)


def filter_de(
    df: pd.DataFrame,
    start: datetime.date,
    end: datetime.date,
    regions: list[str],
    pipelines: list[str],
) -> pd.DataFrame:
    """Return DE rows matching the given date range, regions, and pipelines."""
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    return df[
        (df["date"] >= s) & (df["date"] <= e) &
        (df["region"].isin(regions)) & (df["pipeline"].isin(pipelines))
    ].copy()


def filter_biz(
    df: pd.DataFrame,
    start: datetime.date,
    end: datetime.date,
    regions: list[str],
) -> pd.DataFrame:
    """Return business rows matching the given date range and regions."""
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    return df[
        (df["date"] >= s) & (df["date"] <= e) &
        (df["region"].isin(regions))
    ].copy()


def compute_de_kpis(df: pd.DataFrame) -> dict:
    """Aggregate SLA compliance, volume, error count, and freshness from a filtered DE frame."""
    if df.empty:
        return {"sla_pct": 0.0, "volume_gb": 0.0, "error_count": 0, "freshness_hours": 0.0}
    return {
        "sla_pct": round(float(df["sla_met"].mean() * 100), 1),
        "volume_gb": round(float(df["volume_gb"].sum()), 1),
        "error_count": int(df["error_count"].sum()),
        "freshness_hours": round(float(df["freshness_hours"].mean()), 1),
    }


def compute_biz_kpis(df: pd.DataFrame) -> dict:
    """Aggregate active users, revenue, conversion rate, and sessions from a filtered biz frame."""
    if df.empty:
        return {"active_users": 0, "revenue": 0.0, "conversion_rate": 0.0, "session_count": 0}
    return {
        "active_users": int(df["active_users"].sum()),
        "revenue": round(float(df["revenue"].sum()), 2),
        "conversion_rate": round(float(df["conversion_rate"].mean()), 2),
        "session_count": int(df["session_count"].sum()),
    }
