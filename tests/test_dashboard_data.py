# tests/test_dashboard_data.py
import datetime
import pytest
import pandas as pd
from sg_transit_weather_mesh.notebooks.dashboard_data import (
    ALL_PIPELINES, ALL_REGIONS,
    DEFAULT_START, DEFAULT_END,
    REGION_COORDS,
    generate_de_data, generate_biz_data,
    filter_de, filter_biz,
    compute_de_kpis, compute_biz_kpis,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def df_de():
    return generate_de_data(seed=42)

@pytest.fixture(scope="module")
def df_biz():
    return generate_biz_data(seed=42)


# ── DE mock data shape & contract ────────────────────────────────────────────

def test_de_data_row_count(df_de):
    """31 days × 4 pipelines × 5 regions = 620 rows (May 22 – Jun 21 inclusive)."""
    assert len(df_de) == 31 * len(ALL_PIPELINES) * len(ALL_REGIONS)

def test_de_data_columns(df_de):
    expected = {"date", "pipeline", "region", "sla_met", "volume_gb",
                "error_count", "run_duration_min", "freshness_hours"}
    assert expected.issubset(df_de.columns)

def test_de_data_covers_full_date_range(df_de):
    assert df_de["date"].min() == pd.Timestamp(DEFAULT_START)
    assert df_de["date"].max() == pd.Timestamp(DEFAULT_END)

def test_de_data_pipelines_complete(df_de):
    assert set(df_de["pipeline"].unique()) == set(ALL_PIPELINES)

def test_de_data_regions_complete(df_de):
    assert set(df_de["region"].unique()) == set(ALL_REGIONS)

def test_de_data_value_ranges(df_de):
    assert df_de["volume_gb"].gt(0).all(), "volume_gb must be positive"
    assert df_de["error_count"].ge(0).all(), "error_count must be non-negative"
    assert df_de["run_duration_min"].gt(0).all(), "run_duration_min must be positive"
    assert df_de["freshness_hours"].gt(0).all(), "freshness_hours must be positive"

def test_de_data_sla_met_is_bool(df_de):
    assert df_de["sla_met"].dtype == bool

def test_de_data_deterministic(df_de):
    """Same seed always produces the same SLA compliance."""
    df2 = generate_de_data(seed=42)
    assert df_de["sla_met"].equals(df2["sla_met"])

def test_de_data_different_seeds_differ():
    df_a = generate_de_data(seed=1)
    df_b = generate_de_data(seed=99)
    assert not df_a["sla_met"].equals(df_b["sla_met"])


# ── Business mock data shape & contract ──────────────────────────────────────

def test_biz_data_row_count(df_biz):
    """31 days × 5 regions = 155 rows (May 22 – Jun 21 inclusive)."""
    assert len(df_biz) == 31 * len(ALL_REGIONS)

def test_biz_data_columns(df_biz):
    expected = {"date", "region", "active_users", "session_count",
                "conversions", "revenue", "conversion_rate"}
    assert expected.issubset(df_biz.columns)

def test_biz_data_non_negative_metrics(df_biz):
    for col in ["active_users", "session_count", "conversions", "revenue", "conversion_rate"]:
        assert df_biz[col].ge(0).all(), f"{col} must be non-negative"

def test_biz_data_conversion_rate_bounded(df_biz):
    assert df_biz["conversion_rate"].le(100).all(), "conversion_rate must be ≤ 100%"

def test_biz_data_sessions_gte_conversions(df_biz):
    assert (df_biz["session_count"] >= df_biz["conversions"]).all()

def test_biz_data_upward_user_trend(df_biz):
    """Active users should trend upward over the 30-day window."""
    daily = df_biz.groupby("date")["active_users"].sum()
    first_week = daily.iloc[:7].mean()
    last_week = daily.iloc[-7:].mean()
    assert last_week > first_week


# ── Filter — date range ───────────────────────────────────────────────────────

def test_filter_de_date_range(df_de):
    start = datetime.date(2026, 5, 28)
    end = datetime.date(2026, 6, 4)
    result = filter_de(df_de, start, end, ALL_REGIONS, ALL_PIPELINES)
    assert result["date"].min() >= pd.Timestamp(start)
    assert result["date"].max() <= pd.Timestamp(end)

def test_filter_de_single_day(df_de):
    day = datetime.date(2026, 6, 1)
    result = filter_de(df_de, day, day, ALL_REGIONS, ALL_PIPELINES)
    assert (result["date"] == pd.Timestamp(day)).all()
    assert len(result) == len(ALL_PIPELINES) * len(ALL_REGIONS)

def test_filter_biz_date_range(df_biz):
    start = datetime.date(2026, 6, 1)
    end = datetime.date(2026, 6, 7)
    result = filter_biz(df_biz, start, end, ALL_REGIONS)
    assert result["date"].min() >= pd.Timestamp(start)
    assert result["date"].max() <= pd.Timestamp(end)


# ── Filter — region and pipeline ─────────────────────────────────────────────

def test_filter_de_single_region(df_de):
    result = filter_de(df_de, DEFAULT_START, DEFAULT_END, ["North"], ALL_PIPELINES)
    assert set(result["region"].unique()) == {"North"}

def test_filter_de_single_pipeline(df_de):
    result = filter_de(df_de, DEFAULT_START, DEFAULT_END, ALL_REGIONS, ["api_sync"])
    assert set(result["pipeline"].unique()) == {"api_sync"}

def test_filter_biz_subset_regions(df_biz):
    subset = ["East", "West"]
    result = filter_biz(df_biz, DEFAULT_START, DEFAULT_END, subset)
    assert set(result["region"].unique()) == set(subset)


# ── Filter — empty result ────────────────────────────────────────────────────

def test_filter_de_impossible_date_returns_empty(df_de):
    future = datetime.date(2030, 1, 1)
    result = filter_de(df_de, future, future, ALL_REGIONS, ALL_PIPELINES)
    assert result.empty

def test_filter_biz_impossible_date_returns_empty(df_biz):
    future = datetime.date(2030, 1, 1)
    result = filter_biz(df_biz, future, future, ALL_REGIONS)
    assert result.empty


# ── KPI computations — DE ────────────────────────────────────────────────────

def test_de_kpis_full_dataset(df_de):
    kpis = compute_de_kpis(df_de)
    assert 0.0 <= kpis["sla_pct"] <= 100.0
    assert kpis["volume_gb"] > 0
    assert kpis["error_count"] >= 0
    assert kpis["freshness_hours"] > 0

def test_de_kpis_empty_returns_zeros():
    kpis = compute_de_kpis(pd.DataFrame())
    assert kpis == {"sla_pct": 0.0, "volume_gb": 0.0, "error_count": 0, "freshness_hours": 0.0}

def test_de_kpis_all_sla_met():
    df = pd.DataFrame({"sla_met": [True, True], "volume_gb": [5.0, 3.0],
                        "error_count": [0, 0], "freshness_hours": [1.0, 2.0]})
    assert compute_de_kpis(df)["sla_pct"] == 100.0

def test_de_kpis_no_sla_met():
    df = pd.DataFrame({"sla_met": [False, False], "volume_gb": [5.0, 3.0],
                        "error_count": [10, 8], "freshness_hours": [12.0, 18.0]})
    assert compute_de_kpis(df)["sla_pct"] == 0.0

def test_de_kpis_volume_aggregates_correctly():
    df = pd.DataFrame({"sla_met": [True], "volume_gb": [7.3],
                        "error_count": [0], "freshness_hours": [1.0]})
    assert compute_de_kpis(df)["volume_gb"] == 7.3


# ── KPI computations — Business ──────────────────────────────────────────────

def test_biz_kpis_full_dataset(df_biz):
    kpis = compute_biz_kpis(df_biz)
    assert kpis["active_users"] > 0
    assert kpis["revenue"] > 0
    assert 0.0 <= kpis["conversion_rate"] <= 100.0
    assert kpis["session_count"] > 0

def test_biz_kpis_empty_returns_zeros():
    kpis = compute_biz_kpis(pd.DataFrame())
    assert kpis == {"active_users": 0, "revenue": 0.0, "conversion_rate": 0.0, "session_count": 0}

def test_biz_kpis_revenue_sums_correctly():
    df = pd.DataFrame({
        "active_users": [100, 200], "session_count": [150, 300],
        "conversions": [10, 20], "revenue": [500.0, 1000.0], "conversion_rate": [6.67, 6.67],
    })
    assert compute_biz_kpis(df)["revenue"] == 1500.0

def test_biz_kpis_conversion_rate_is_mean():
    df = pd.DataFrame({
        "active_users": [100, 100], "session_count": [100, 100],
        "conversions": [5, 10], "revenue": [100.0, 200.0], "conversion_rate": [4.0, 8.0],
    })
    assert compute_biz_kpis(df)["conversion_rate"] == 6.0


# ── REGION_COORDS contract ────────────────────────────────────────────────────

def test_region_coords_covers_all_regions():
    """Every region in ALL_REGIONS must have an entry in REGION_COORDS."""
    assert set(REGION_COORDS.keys()) == set(ALL_REGIONS)


def test_region_coords_within_singapore_bounds():
    """All region centroids must lie within the bounding box of Singapore island.

    Lat: 1.15 – 1.50  |  Lon: 103.60 – 104.05
    """
    LAT_MIN, LAT_MAX = 1.15, 1.50
    LON_MIN, LON_MAX = 103.60, 104.05
    for region, (lat, lon) in REGION_COORDS.items():
        assert LAT_MIN <= lat <= LAT_MAX, f"{region} lat {lat} out of Singapore bounds"
        assert LON_MIN <= lon <= LON_MAX, f"{region} lon {lon} out of Singapore bounds"
