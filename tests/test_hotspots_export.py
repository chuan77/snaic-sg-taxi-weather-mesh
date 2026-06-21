"""Tests for hotspot demand ranking and geo-distance helpers in analytics.py."""
import math
import pytest

from sg_transit_weather_mesh.assets.analytics import (
    HOTSPOT_ZONES,
    _dist_km,
    _count_taxis_per_zone,
    _rank_hotspots,
)


# ---------------------------------------------------------------------------
# HOTSPOT_ZONES shape
# ---------------------------------------------------------------------------

def test_hotspot_zones_has_six_entries():
    assert len(HOTSPOT_ZONES) == 6


def test_hotspot_zones_required_keys():
    for zone in HOTSPOT_ZONES:
        for key in ("id", "name", "lat", "lng", "radius_km"):
            assert key in zone, f"Zone {zone.get('id')} missing key {key}"


def test_hotspot_zones_unique_ids():
    ids = [z["id"] for z in HOTSPOT_ZONES]
    assert len(ids) == len(set(ids))


def test_hotspot_zones_coordinates_within_singapore():
    """All hotspot centres must lie within the rough bounding box of Singapore."""
    for zone in HOTSPOT_ZONES:
        assert 1.15 <= zone["lat"] <= 1.48, f"{zone['name']} lat out of range"
        assert 103.6 <= zone["lng"] <= 104.1, f"{zone['name']} lng out of range"


# ---------------------------------------------------------------------------
# _dist_km
# ---------------------------------------------------------------------------

def test_dist_km_same_point_is_zero():
    assert _dist_km(1.3, 103.8, 1.3, 103.8) == pytest.approx(0.0)


def test_dist_km_known_distance():
    # ~1.0 degree latitude ≈ 111 km
    d = _dist_km(0.0, 0.0, 1.0, 0.0)
    assert d == pytest.approx(111.0, rel=0.01)


def test_dist_km_symmetric():
    d1 = _dist_km(1.28, 103.85, 1.36, 103.99)
    d2 = _dist_km(1.36, 103.99, 1.28, 103.85)
    assert d1 == pytest.approx(d2)


def test_dist_km_marina_to_changi_approx():
    # Marina Bay to Changi Airport straight-line ≈ 17 km
    d = _dist_km(1.2897, 103.8501, 1.3592, 103.9894)
    assert 15.0 <= d <= 20.0


# ---------------------------------------------------------------------------
# _count_taxis_per_zone
# ---------------------------------------------------------------------------

def test_count_taxis_empty_rows():
    result = _count_taxis_per_zone([], HOTSPOT_ZONES)
    assert all(z["taxi_count"] == 0 for z in result)


def test_count_taxis_within_radius():
    zones = [{"id": "z1", "name": "Test", "lat": 1.30, "lng": 103.80, "radius_km": 1.0}]
    # Taxi exactly at zone centre — should be counted
    rows = [(1.30, 103.80)]
    result = _count_taxis_per_zone(rows, zones)
    assert result[0]["taxi_count"] == 1


def test_count_taxis_outside_radius():
    zones = [{"id": "z1", "name": "Test", "lat": 1.30, "lng": 103.80, "radius_km": 0.5}]
    # ~15 km away
    rows = [(1.30, 104.0)]
    result = _count_taxis_per_zone(rows, zones)
    assert result[0]["taxi_count"] == 0


def test_count_taxis_boundary_edge():
    zones = [{"id": "z1", "name": "Test", "lat": 1.30, "lng": 103.80, "radius_km": 1.0}]
    # ~111 km * 0.009 lat degrees ≈ 1.0 km, just inside
    inside_lat = 1.30 + (0.9 / 111.0)
    rows = [(inside_lat, 103.80)]
    result = _count_taxis_per_zone(rows, zones)
    assert result[0]["taxi_count"] == 1


def test_count_taxis_skips_none_coordinates():
    zones = [{"id": "z1", "name": "Test", "lat": 1.30, "lng": 103.80, "radius_km": 1.0}]
    rows = [(None, None), (None, 103.80), (1.30, None)]
    result = _count_taxis_per_zone(rows, zones)
    assert result[0]["taxi_count"] == 0


def test_count_taxis_preserves_zone_count():
    result = _count_taxis_per_zone([], HOTSPOT_ZONES)
    assert len(result) == len(HOTSPOT_ZONES)


def test_count_taxis_multiple_zones():
    zones = [
        {"id": "a", "name": "A", "lat": 1.28, "lng": 103.85, "radius_km": 1.0},
        {"id": "b", "name": "B", "lat": 1.36, "lng": 103.99, "radius_km": 1.0},
    ]
    rows = [(1.28, 103.85), (1.28, 103.85), (1.36, 103.99)]  # 2 in A, 1 in B
    result = _count_taxis_per_zone(rows, zones)
    counts = {z["id"]: z["taxi_count"] for z in result}
    assert counts["a"] == 2
    assert counts["b"] == 1


# ---------------------------------------------------------------------------
# _rank_hotspots
# ---------------------------------------------------------------------------

def test_rank_hotspots_assigns_all_levels():
    zones = [
        {**z, "taxi_count": i * 10}
        for i, z in enumerate(HOTSPOT_ZONES)
    ]
    result = _rank_hotspots(zones)
    levels = {z["level"] for z in result}
    assert levels == {"high", "medium", "low"}


def test_rank_hotspots_highest_count_gets_high():
    zones = [
        {"id": "h1", "name": "A", "lat": 1.28, "lng": 103.85, "radius_km": 1.0, "taxi_count": 100},
        {"id": "h2", "name": "B", "lat": 1.30, "lng": 103.80, "radius_km": 1.0, "taxi_count": 50},
        {"id": "h3", "name": "C", "lat": 1.35, "lng": 103.75, "radius_km": 1.0, "taxi_count": 10},
    ]
    result = _rank_hotspots(zones)
    level_map = {z["id"]: z["level"] for z in result}
    assert level_map["h1"] == "high"
    assert level_map["h3"] == "low"


def test_rank_hotspots_empty_input():
    assert _rank_hotspots([]) == []


def test_rank_hotspots_preserves_original_order():
    zones = [
        {"id": "h1", "name": "A", "lat": 1.28, "lng": 103.85, "radius_km": 1.0, "taxi_count": 5},
        {"id": "h2", "name": "B", "lat": 1.30, "lng": 103.80, "radius_km": 1.0, "taxi_count": 50},
        {"id": "h3", "name": "C", "lat": 1.35, "lng": 103.75, "radius_km": 1.0, "taxi_count": 20},
    ]
    result = _rank_hotspots(zones)
    assert [z["id"] for z in result] == ["h1", "h2", "h3"]


def test_rank_hotspots_six_zones_gives_two_each():
    zones = [
        {**z, "taxi_count": i}
        for i, z in enumerate(HOTSPOT_ZONES)
    ]
    result = _rank_hotspots(zones)
    from collections import Counter
    counts = Counter(z["level"] for z in result)
    assert counts["high"] == 2
    assert counts["medium"] == 2
    assert counts["low"] == 2


def test_rank_hotspots_all_zero_still_assigns_levels():
    zones = [{**z, "taxi_count": 0} for z in HOTSPOT_ZONES]
    result = _rank_hotspots(zones)
    assert all("level" in z for z in result)
