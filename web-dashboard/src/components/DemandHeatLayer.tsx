import { useEffect, useCallback, useRef } from 'react';
import { useMap } from 'react-leaflet';
import type { TaxiPoint } from '../types';

// Singapore bounding box
const LAT_MIN = 1.15, LAT_MAX = 1.48;
const LNG_MIN = 103.60, LNG_MAX = 104.10;
const CELL = 0.005; // ~556 m per cell
const GRID_H = Math.ceil((LAT_MAX - LAT_MIN) / CELL); // ~66
const GRID_W = Math.ceil((LNG_MAX - LNG_MIN) / CELL); // ~100
const BLUR_R = 4;

function boxBlur(src: Float32Array, w: number, h: number, r: number): Float32Array {
  const tmp = new Float32Array(w * h);
  const out = new Float32Array(w * h);
  const d = 2 * r + 1;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      let s = 0;
      for (let k = -r; k <= r; k++) s += src[y * w + Math.min(w - 1, Math.max(0, x + k))];
      tmp[y * w + x] = s / d;
    }
  }
  for (let x = 0; x < w; x++) {
    for (let y = 0; y < h; y++) {
      let s = 0;
      for (let k = -r; k <= r; k++) s += tmp[Math.min(h - 1, Math.max(0, y + k)) * w + x];
      out[y * w + x] = s / d;
    }
  }
  return out;
}

// Blue → Cyan → Yellow → Orange → Red colormap
function heatColor(t: number): string {
  let r = 0, g = 0, b = 0, a = 0;
  if (t < 0.25) {
    const s = t / 0.25;
    r = 0; g = Math.round(s * 180); b = 255; a = Math.round(60 + s * 110);
  } else if (t < 0.5) {
    const s = (t - 0.25) / 0.25;
    r = 0; g = 255; b = Math.round((1 - s) * 255); a = 170;
  } else if (t < 0.75) {
    const s = (t - 0.5) / 0.25;
    r = Math.round(s * 255); g = 255; b = 0; a = 195;
  } else {
    const s = (t - 0.75) / 0.25;
    r = 255; g = Math.round((1 - s) * 200); b = 0; a = 215;
  }
  return `rgba(${r},${g},${b},${(a / 255).toFixed(2)})`;
}

// Precomputed colormap string lookup (256 entries)
const COLORMAP = Array.from({ length: 256 }, (_, i) => heatColor(i / 255));

interface Props { taxis: TaxiPoint[]; }

export default function DemandHeatLayer({ taxis }: Props): null {
  const map = useMap();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const blurredRef = useRef<Float32Array>(new Float32Array(GRID_H * GRID_W));
  const maxRef = useRef(0);

  // Recompute density grid + blur only when taxi data changes
  useEffect(() => {
    const density = new Float32Array(GRID_H * GRID_W);
    for (const taxi of taxis) {
      const gy = Math.floor((taxi.lat - LAT_MIN) / CELL);
      const gx = Math.floor((taxi.lng - LNG_MIN) / CELL);
      if (gx >= 0 && gx < GRID_W && gy >= 0 && gy < GRID_H) {
        density[gy * GRID_W + gx]++;
      }
    }
    const blurred = boxBlur(density, GRID_W, GRID_H, BLUR_R);
    let max = 0;
    for (let i = 0; i < blurred.length; i++) if (blurred[i] > max) max = blurred[i];
    blurredRef.current = blurred;
    maxRef.current = max;
  }, [taxis]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || maxRef.current === 0) return;
    const size = map.getSize();
    canvas.width = size.x;
    canvas.height = size.y;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, size.x, size.y);

    // Compute pixel scale from 3 reference points (valid for current zoom + pan)
    const ref0   = map.latLngToContainerPoint([LAT_MIN, LNG_MIN]);
    const refLat = map.latLngToContainerPoint([LAT_MIN + CELL, LNG_MIN]);
    const refLng = map.latLngToContainerPoint([LAT_MIN, LNG_MIN + CELL]);
    const pxH = ref0.y - refLat.y; // pixels per cell in Y (lat goes up, y goes down)
    const pxW = refLng.x - ref0.x; // pixels per cell in X

    const blurred = blurredRef.current;
    const max = maxRef.current;
    const THRESHOLD = 0.04;

    for (let gy = 0; gy < GRID_H; gy++) {
      // SW corner Y of this row (lat increases up → screen Y decreases)
      const swY = ref0.y - gy * pxH;
      if (swY + pxH < 0 || swY - pxH > size.y) continue; // cull off-screen rows

      for (let gx = 0; gx < GRID_W; gx++) {
        const t = blurred[gy * GRID_W + gx] / max;
        if (t < THRESHOLD) continue;

        const swX = ref0.x + gx * pxW;
        if (swX + pxW < 0 || swX > size.x) continue; // cull off-screen cols

        const tNorm = (t - THRESHOLD) / (1 - THRESHOLD);
        ctx.fillStyle = COLORMAP[Math.min(255, Math.floor(tNorm * 255))];
        ctx.fillRect(swX, swY - pxH, pxW + 0.5, pxH + 0.5); // +0.5 closes seams
      }
    }
  }, [map]);

  useEffect(() => {
    const container = map.getContainer();
    const canvas = document.createElement('canvas');
    canvas.style.cssText = 'position:absolute;top:0;left:0;pointer-events:none;';
    canvas.style.zIndex = '440';
    container.appendChild(canvas);
    canvasRef.current = canvas;

    draw();
    map.on('move', draw);
    map.on('zoom', draw);
    map.on('resize', draw);

    return () => {
      map.off('move', draw);
      map.off('zoom', draw);
      map.off('resize', draw);
      canvas.remove();
      canvasRef.current = null;
    };
  }, [map, draw]);

  useEffect(() => { draw(); }, [taxis, draw]);

  return null;
}
