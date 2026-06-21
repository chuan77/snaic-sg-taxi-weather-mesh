# tests/test_nowcast_export.py
import json
import pytest
from sg_transit_weather_mesh.assets.analytics import (
    FORECAST_INTENSITY,
    AREA_REGION,
    INTENSITY_RANK,
    _classify_areas,
    _aggregate_regions,
    _build_alert,
    _build_timeline,
)

# All 47 NEA area names from the v2 API
ALL_NEA_AREAS = [
    "Ang Mo Kio", "Bedok", "Bishan", "Boon Lay", "Bukit Batok",
    "Bukit Merah", "Bukit Panjang", "Bukit Timah", "Central Water Catchment",
    "Changi", "Choa Chu Kang", "City", "Clementi", "Geylang", "Hougang",
    "Jalan Bahar", "Jurong East", "Jurong Island", "Jurong West", "Kallang",
    "Lim Chu Kang", "Mandai", "Marine Parade", "Novena", "Pasir Ris",
    "Paya Lebar", "Pioneer", "Pulau Tekong", "Pulau Ubin", "Punggol",
    "Queenstown", "Seletar", "Sembawang", "Sengkang", "Sentosa", "Serangoon",
    "Southern Islands", "Sungei Kadut", "Tampines", "Tanglin", "Tengah",
    "Toa Payoh", "Tuas", "Western Islands", "Western Water Catchment",
    "Woodlands", "Yishun",
]

ALL_VALID_INTENSITIES = {"clear", "drizzle", "moderate", "heavy", "storm"}
ALL_VALID_REGIONS = {"North", "South", "East", "West", "Central"}


# ── FORECAST_INTENSITY mapping ────────────────────────────────────────────────

def test_forecast_intensity_all_values_are_valid():
    """Every mapped intensity must be a recognised frontend WeatherIntensity."""
    for forecast, intensity in FORECAST_INTENSITY.items():
        assert intensity in ALL_VALID_INTENSITIES, (
            f"'{forecast}' maps to unknown intensity '{intensity}'"
        )


def test_forecast_intensity_storm_entries():
    assert FORECAST_INTENSITY["Thundery Showers"] == "storm"
    assert FORECAST_INTENSITY["Heavy Thundery Showers"] == "storm"
    assert FORECAST_INTENSITY["Heavy Thundery Showers with Gusty Winds"] == "storm"


def test_forecast_intensity_clear_entries():
    assert FORECAST_INTENSITY["Fair"] == "clear"
    assert FORECAST_INTENSITY["Partly Cloudy (Day)"] == "clear"
    assert FORECAST_INTENSITY["Fair & Warm"] == "clear"


def test_forecast_intensity_escalation_ordering():
    """Showers must outrank Cloudy, and Thundery Showers must outrank Showers."""
    assert INTENSITY_RANK[FORECAST_INTENSITY["Showers"]] > INTENSITY_RANK[FORECAST_INTENSITY["Cloudy"]]
    assert INTENSITY_RANK[FORECAST_INTENSITY["Thundery Showers"]] > INTENSITY_RANK[FORECAST_INTENSITY["Showers"]]


def test_unknown_forecast_defaults_to_drizzle_in_classify():
    rows = [("Bishan", "Overcast with Sprinkles", 1.35, 103.84, "2026-06-21T08:00:00+08:00")]
    areas, *_ = _classify_areas(rows, has_valid_period=False)
    assert areas[0]["intensity"] == "drizzle"


# ── AREA_REGION mapping ───────────────────────────────────────────────────────

def test_area_region_covers_all_47_nea_areas():
    missing = [a for a in ALL_NEA_AREAS if a not in AREA_REGION]
    assert missing == [], f"Missing region mapping for: {missing}"


def test_area_region_all_regions_valid():
    for area, region in AREA_REGION.items():
        assert region in ALL_VALID_REGIONS, f"'{area}' mapped to invalid region '{region}'"


def test_area_region_spot_checks():
    assert AREA_REGION["Changi"] == "East"
    assert AREA_REGION["Sentosa"] == "South"
    assert AREA_REGION["Woodlands"] == "North"
    assert AREA_REGION["Jurong West"] == "West"
    assert AREA_REGION["Bishan"] == "Central"


def test_area_region_covers_all_five_planning_regions():
    regions_covered = set(AREA_REGION.values())
    assert regions_covered == ALL_VALID_REGIONS


# ── _classify_areas ───────────────────────────────────────────────────────────

def test_classify_areas_v2_schema():
    rows = [(
        "Bishan", "Thundery Showers", 1.35, 103.84,
        "2026-06-21T08:00:00+08:00",
        "2026-06-21T08:00:00+08:00",
        "2026-06-21T10:00:00+08:00",
        "8.00 am to 10.00 am",
        "2026-06-21T08:05:00+08:00",
    )]
    areas, vp_start, vp_end, vp_text, update_ts = _classify_areas(rows, has_valid_period=True)
    assert len(areas) == 1
    assert areas[0]["name"] == "Bishan"
    assert areas[0]["intensity"] == "storm"
    assert areas[0]["region"] == "Central"
    assert vp_start == "2026-06-21T08:00:00+08:00"
    assert vp_end == "2026-06-21T10:00:00+08:00"
    assert vp_text == "8.00 am to 10.00 am"
    assert update_ts == "2026-06-21T08:05:00+08:00"


def test_classify_areas_v1_fallback_schema():
    rows = [("Tampines", "Cloudy", 1.35, 103.94, "2026-06-21T08:00:00+08:00")]
    areas, vp_start, vp_end, vp_text, _ = _classify_areas(rows, has_valid_period=False)
    assert areas[0]["region"] == "East"
    assert areas[0]["intensity"] == "drizzle"
    assert vp_text == "2-hour forecast"


def test_classify_areas_unknown_area_defaults_to_central():
    rows = [("Unknown Island", "Fair", 1.30, 103.80, "2026-06-21T08:00:00+08:00")]
    areas, *_ = _classify_areas(rows, has_valid_period=False)
    assert areas[0]["region"] == "Central"


# ── _aggregate_regions ────────────────────────────────────────────────────────

def test_aggregate_regions_picks_highest_intensity():
    areas = [
        {"name": "Bishan",   "region": "Central", "intensity": "moderate", "forecast": "Showers",         "latitude": 1.35, "longitude": 103.84},
        {"name": "Novena",   "region": "Central", "intensity": "storm",    "forecast": "Thundery Showers", "latitude": 1.32, "longitude": 103.84},
        {"name": "Tampines", "region": "East",    "intensity": "clear",    "forecast": "Fair",             "latitude": 1.35, "longitude": 103.94},
    ]
    regions = _aggregate_regions(areas)
    assert regions["Central"] == "storm"
    assert regions["East"] == "clear"


def test_aggregate_regions_returns_all_five_regions():
    areas = [{"name": "Bishan", "region": "Central", "intensity": "drizzle",
              "forecast": "Cloudy", "latitude": 1.35, "longitude": 103.84}]
    regions = _aggregate_regions(areas)
    assert set(regions.keys()) == {"North", "South", "East", "West", "Central"}


def test_aggregate_regions_empty_areas_defaults_to_clear():
    regions = _aggregate_regions([])
    for v in regions.values():
        assert v == "clear"


# ── _build_alert ──────────────────────────────────────────────────────────────

def test_build_alert_storm_in_central_south():
    regions = {"North": "clear", "South": "storm", "East": "drizzle", "West": "clear", "Central": "moderate"}
    alert = _build_alert(regions)
    assert alert["active"] is True
    assert "Thunderstorms" in alert["message"]
    assert "Central" in alert["message"] or "South" in alert["message"]


def test_build_alert_storm_in_central():
    regions = {"North": "clear", "South": "clear", "East": "drizzle", "West": "clear", "Central": "storm"}
    alert = _build_alert(regions)
    assert alert["active"] is True
    assert "Thunderstorms" in alert["message"]


def test_build_alert_heavy_rain_central_south():
    regions = {"North": "drizzle", "South": "heavy", "East": "clear", "West": "drizzle", "Central": "heavy"}
    alert = _build_alert(regions)
    assert alert["active"] is True
    assert "Heavy rain" in alert["message"]


def test_build_alert_storm_only_north():
    regions = {"North": "storm", "South": "drizzle", "East": "clear", "West": "clear", "Central": "clear"}
    alert = _build_alert(regions)
    assert alert["active"] is True
    assert "Thunderstorms" in alert["message"]
    assert "North" in alert["message"]


def test_build_alert_moderate_showers_only():
    regions = {"North": "moderate", "South": "drizzle", "East": "clear", "West": "moderate", "Central": "drizzle"}
    alert = _build_alert(regions)
    assert alert["active"] is False
    assert "Showers" in alert["message"]


def test_build_alert_fair_conditions():
    regions = {"North": "clear", "South": "clear", "East": "clear", "West": "clear", "Central": "clear"}
    alert = _build_alert(regions)
    assert alert["active"] is False
    assert "fair" in alert["message"].lower()


# ── _build_timeline ───────────────────────────────────────────────────────────

def test_build_timeline_derives_three_steps():
    timeline = _build_timeline(
        "2026-06-21T11:00:00+08:00",
        "2026-06-21T13:00:00+08:00",
        "moderate",
    )
    assert len(timeline) == 3
    # All steps share the same condition label for the 2-hour forecast window
    assert all(s["label"] == "Showers" for s in timeline)


def test_build_timeline_all_steps_have_same_intensity():
    timeline = _build_timeline(
        "2026-06-21T11:00:00+08:00",
        "2026-06-21T13:00:00+08:00",
        "storm",
    )
    assert all(s["intensity"] == "storm" for s in timeline)


def test_build_timeline_start_time_formatted():
    timeline = _build_timeline(
        "2026-06-21T11:00:00+08:00",
        "2026-06-21T13:00:00+08:00",
        "drizzle",
    )
    assert timeline[0]["time"] == "11:00 AM"


def test_build_timeline_end_time_formatted():
    timeline = _build_timeline(
        "2026-06-21T11:00:00+08:00",
        "2026-06-21T13:00:00+08:00",
        "drizzle",
    )
    assert timeline[2]["time"] == "1:00 PM"


def test_build_timeline_mid_point_is_one_hour():
    timeline = _build_timeline(
        "2026-06-21T11:00:00+08:00",
        "2026-06-21T13:00:00+08:00",
        "clear",
    )
    assert timeline[1]["time"] == "12:00 PM"


def test_build_timeline_invalid_timestamps_fall_back_gracefully():
    timeline = _build_timeline("not-a-date", "also-not-a-date", "moderate")
    assert len(timeline) == 3
    assert all("intensity" in s for s in timeline)


# ── nowcast.json schema ───────────────────────────────────────────────────────

def test_nowcast_json_has_required_keys(tmp_path):
    """Verifies that _classify_areas + _aggregate_regions + _build_alert compose into
    a structurally valid nowcast payload."""
    rows = [
        ("Bishan",   "Thundery Showers", 1.35, 103.84, "2026-06-21T11:00:00+08:00",
         "2026-06-21T11:00:00+08:00", "2026-06-21T13:00:00+08:00",
         "11.00 am to 1.00 pm", "2026-06-21T11:05:00+08:00"),
        ("Tampines", "Cloudy",           1.35, 103.94, "2026-06-21T11:00:00+08:00",
         "2026-06-21T11:00:00+08:00", "2026-06-21T13:00:00+08:00",
         "11.00 am to 1.00 pm", "2026-06-21T11:05:00+08:00"),
    ]
    areas, vp_start, vp_end, vp_text, update_ts = _classify_areas(rows, has_valid_period=True)
    regions = _aggregate_regions(areas)
    alert = _build_alert(regions)
    timeline = _build_timeline(vp_start, vp_end, "storm")

    nowcast = {
        "updated_at": update_ts,
        "valid_period": {"start": vp_start, "end": vp_end, "text": vp_text},
        "alert": alert,
        "regions": regions,
        "areas": areas,
        "timeline": timeline,
    }

    # Validate JSON serialisability
    json_str = json.dumps(nowcast, ensure_ascii=False)
    parsed = json.loads(json_str)

    assert "updated_at" in parsed
    assert "valid_period" in parsed
    assert "alert" in parsed
    assert "regions" in parsed
    assert "areas" in parsed
    assert "timeline" in parsed
    assert len(parsed["timeline"]) == 3
    assert set(parsed["regions"].keys()) == {"North", "South", "East", "West", "Central"}
    assert isinstance(parsed["alert"]["active"], bool)
