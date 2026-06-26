# Taxi Cluster — Configurable Time Window Selector

**Date:** 2026-06-25
**Status:** Approved

## Context

The Taxi Cluster page currently shows a choropleth of distinct taxi positions visited in the last 30 minutes. The metric is misleading — it reads as "visit density" rather than taxi availability. The goal is to reframe the data as "taxi activity in the last N minutes" and allow the user to switch between a 15-minute and 30-minute lookback window.

**Labelling decision:** The LTA Taxi Availability API does not expose taxi IDs — only `(lat, lng)` coordinates. This makes true "distinct taxi" counting impossible. A spatial bucketing approach (rounding to 3dp ≈ 111m grid cells) was considered but rejected: it under-counts at dense hubs like Changi (200 taxis circulating a 300m zone → at most ~9 grid cells). The existing `DISTINCT lat, lng` at 4dp (~11m) is a better relative density signal. The UI label uses "taxi activity" to accurately reflect what is being measured.

The 5-minute and 10-minute windows are deferred until the 15/30 min implementation is validated for query load and data quality (Dagster syncs every 5 min, so a 5-min window captures only ~1 snapshot).

## Approach

Keep browser-side point-in-polygon (PIP). The backend exports two separate JSON files. The frontend adds a pill selector to switch between them. No DuckDB schema changes, no mart tables, no spatial SQL.

## Backend

**File:** `sg_transit_weather_mesh/assets/analytics.py` — `taxi_window_export` asset

- Run two queries in the same asset execution, each using `DISTINCT latitude, longitude` with the appropriate interval:
  - `WHERE timestamp >= MAX(timestamp) - INTERVAL 15 MINUTE` → `taxis_window_15.json`
  - `WHERE timestamp >= MAX(timestamp) - INTERVAL 30 MINUTE` → `taxis_window_30.json`
- Retire `taxis_window.json` — update the `_TAXIS_WINDOW_JSON` path constant to become two constants: `_TAXIS_WINDOW_15_JSON` and `_TAXIS_WINDOW_30_JSON`.
- Asset metadata logs both taxi counts.
- JSON contract (same for both files):
  ```json
  { "window_minutes": 15, "total": 4823, "taxis": [{"lat": 1.3521, "lng": 103.8198}] }
  ```

## Frontend

### Hook: `useWindowTaxis.ts`

Add a `windowMinutes: 15 | 30` parameter. The hook fetches `/data/taxis_window_15.json` or `/data/taxis_window_30.json` based on the argument. Re-fetches when `windowMinutes` changes (add it to the `useEffect` dependency array). Poll interval stays at 5 min.

### Component: `TaxiClusterPage.tsx`

- Add `const [windowMinutes, setWindowMinutes] = useState<15 | 30>(30)`.
- Render a pill selector above the choropleth map: **"15 min | 30 min"** — active pill uses a filled/highlighted style.
- Pass `windowMinutes` to `useWindowTaxis`.
- Update the subtitle label: `"Taxi activity — last {windowMinutes} min"`.
- No changes to `useSubzoneCounts`, the PIP algorithm, the choropleth render, or the top-20 table.

### Types: `types/index.ts`

No changes required — `TaxiPoint` and `WindowTaxisData` already match the new contract.

## Files Changed

| File | Change |
|---|---|
| `sg_transit_weather_mesh/assets/analytics.py` | Two queries + two output paths in `taxi_window_export` |
| `web-dashboard/src/hooks/useWindowTaxis.ts` | Add `windowMinutes` param; dynamic fetch URL |
| `web-dashboard/src/components/TaxiClusterPage.tsx` | Pill selector state + UI; updated subtitle |

**Unchanged:** `useSubzoneCounts.ts`, `types/index.ts`, `sg_subzones.geojson`, DuckDB schema, all other assets.

## Verification

1. Run `uv run dagster job execute -j sg_taxi_weather_sync_job` — confirm both `taxis_window_15.json` and `taxis_window_30.json` are written to `web-dashboard/public/data/`.
2. Verify `window_minutes` field matches the file suffix in each output.
3. Start the Vite dev server (`cd web-dashboard && npm run dev`), open the Taxi Cluster page.
4. Toggle between "15 min" and "30 min" pills — confirm the choropleth re-renders with different counts (15-min should show fewer or equal taxis than 30-min).
5. Run `cd web-dashboard && npx tsc --noEmit` — 0 errors.
6. Run `uv run pytest tests -v` — all tests pass.
