import type { WeatherCell, WeatherIntensity } from '../types';

// 4 rows × 5 cols grid covering Singapore island
// Lat rows (south → north): [1.18, 1.26], [1.26, 1.33], [1.33, 1.40], [1.40, 1.47]
// Lng cols (west → east):   [103.58, 103.68], [103.68, 103.78], [103.78, 103.88], [103.88, 103.98], [103.98, 104.08]
// Pattern: clear in west, escalates to storm in central/east

const GRID: WeatherIntensity[][] = [
  // row 0 = south (lat 1.18-1.26)
  ['drizzle', 'moderate', 'moderate', 'storm', 'storm'],
  // row 1 = central-south (lat 1.26-1.33)
  ['clear', 'moderate', 'heavy', 'storm', 'storm'],
  // row 2 = central-north (lat 1.33-1.40) — Jurong clear, Orchard/Novena heavy
  ['clear', 'drizzle', 'moderate', 'heavy', 'storm'],
  // row 3 = north (lat 1.40-1.47)
  ['clear', 'drizzle', 'drizzle', 'moderate', 'moderate'],
];

const LAT_EDGES = [1.18, 1.26, 1.33, 1.40, 1.47];
const LNG_EDGES = [103.58, 103.68, 103.78, 103.88, 103.98, 104.08];

export const WEATHER_CELLS: WeatherCell[] = GRID.flatMap((row, ri) =>
  row.map((intensity, ci) => ({
    id: `cell-${ri}-${ci}`,
    bounds: [
      [LAT_EDGES[ri], LNG_EDGES[ci]],         // SW: south lat, west lng
      [LAT_EDGES[ri + 1], LNG_EDGES[ci + 1]], // NE: north lat, east lng
    ],
    intensity,
  }))
);

export const INTENSITY_STYLE: Record<
  WeatherIntensity,
  { fillColor: string; color: string; fillOpacity: number; weight: number; opacity: number; className: string }
> = {
  clear:    { fillColor: '#06b6d4', color: '#06b6d4', fillOpacity: 0.05, weight: 0.4, opacity: 0.20, className: '' },
  drizzle:  { fillColor: '#38bdf8', color: '#7dd3fc', fillOpacity: 0.12, weight: 0.5, opacity: 0.30, className: 'wx-drizzle' },
  moderate: { fillColor: '#6366f1', color: '#818cf8', fillOpacity: 0.18, weight: 0.8, opacity: 0.40, className: 'wx-moderate' },
  heavy:    { fillColor: '#a855f7', color: '#c084fc', fillOpacity: 0.26, weight: 1.0, opacity: 0.55, className: 'wx-heavy' },
  storm:    { fillColor: '#ec4899', color: '#f472b6', fillOpacity: 0.34, weight: 1.5, opacity: 0.65, className: 'wx-storm' },
};

// Area label markers for the map
export const AREA_LABELS: { pos: [number, number]; label: string; main?: boolean }[] = [
  { pos: [1.338, 103.700], label: 'Jurong' },
  { pos: [1.304, 103.832], label: 'Orchard Road' },
  { pos: [1.358, 103.988], label: 'Changi' },
  { pos: [1.352, 103.819], label: 'SINGAPORE', main: true },
];
