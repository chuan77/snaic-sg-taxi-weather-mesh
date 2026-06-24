import { useEffect, useRef, useCallback } from 'react';
import { useMap } from 'react-leaflet';
import type { NowcastArea, WeatherIntensity } from '../types';

// Colours matching INTENSITY_STYLE in data/weather.ts
const CFG: Record<WeatherIntensity, { rgb: [number, number, number]; maxAlpha: number } | null> = {
  clear:    null,
  drizzle:  { rgb: [56,  189, 248], maxAlpha: 0.22 },  // #38bdf8 sky-blue
  moderate: { rgb: [99,  102, 241], maxAlpha: 0.34 },  // #6366f1 indigo
  heavy:    { rgb: [168,  85, 247], maxAlpha: 0.48 },  // #a855f7 purple
  storm:    { rgb: [236,  72, 153], maxAlpha: 0.64 },  // #ec4899 magenta
};

// Paint weakest intensity first so storm blobs render on top
const DRAW_ORDER: WeatherIntensity[] = ['drizzle', 'moderate', 'heavy', 'storm'];

interface Props {
  areas: NowcastArea[];
}

/**
 * Canvas overlay rendering a smooth radial-gradient "weather blob" centred on
 * each NEA area coordinate. Appended to map.getContainer() (z-index 400), same
 * pattern as TaxiDotLayer/DemandHeatLayer, to avoid CSS transform desync during pan.
 */
export function PrecipitationOverlay({ areas }: Props): null {
  const map      = useMap();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const areasRef  = useRef<NowcastArea[]>(areas);
  areasRef.current = areas;   // keep in sync without re-subscribing events

  // ── Inject canvas into Leaflet overlayPane on mount ───────────────────────
  useEffect(() => {
    const container = map.getContainer();
    const canvas = document.createElement('canvas');
    canvas.style.position      = 'absolute';
    canvas.style.top           = '0';
    canvas.style.left          = '0';
    canvas.style.zIndex        = '400';
    canvas.style.pointerEvents = 'none';
    container.appendChild(canvas);
    canvasRef.current = canvas;
    return () => {
      canvas.remove();
      canvasRef.current = null;
    };
  }, [map]);

  // ── Core draw routine ─────────────────────────────────────────────────────
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const size = map.getSize();
    canvas.width  = size.x;
    canvas.height = size.y;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, size.x, size.y);

    // Sort: weaker intensities painted first → storm visible on top
    const sorted = [...areasRef.current].sort(
      (a, b) => DRAW_ORDER.indexOf(a.intensity) - DRAW_ORDER.indexOf(b.intensity),
    );

    for (const area of sorted) {
      const cfg = CFG[area.intensity];
      if (!cfg || !area.latitude) continue;

      // Convert geo-coordinates to canvas pixel position
      const pt = map.latLngToContainerPoint([area.latitude, area.longitude]);

      // Radius ≈ 5 km expressed in screen pixels at the current zoom level
      const edgePt = map.latLngToContainerPoint([area.latitude + 0.045, area.longitude]);
      const radius = Math.max(18, Math.abs(pt.y - edgePt.y) * 1.6);

      const { rgb: [r, g, b], maxAlpha } = cfg;
      const grad = ctx.createRadialGradient(pt.x, pt.y, 0, pt.x, pt.y, radius);
      grad.addColorStop(0,    `rgba(${r},${g},${b},${maxAlpha})`);
      grad.addColorStop(0.50, `rgba(${r},${g},${b},${+(maxAlpha * 0.4).toFixed(3)})`);
      grad.addColorStop(1,    `rgba(${r},${g},${b},0)`);

      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, radius, 0, Math.PI * 2);
      ctx.fill();
    }
  }, [map]);

  // ── Subscribe to map viewport events with direct Leaflet API ──────────────
  useEffect(() => {
    map.on('move',   draw);
    map.on('zoom',   draw);
    map.on('resize', draw);
    draw(); // initial render
    return () => {
      map.off('move',   draw);
      map.off('zoom',   draw);
      map.off('resize', draw);
    };
  }, [map, draw]);

  // ── Redraw when nowcast data refreshes ────────────────────────────────────
  useEffect(() => {
    draw();
  }, [draw, areas]);

  return null;
}
