import { useEffect, useCallback, useRef } from 'react';
import { useMap } from 'react-leaflet';
import type { TaxiPoint } from '../types';

interface Props {
  taxis: TaxiPoint[];
}

export default function TaxiDotLayer({ taxis }: Props): null {
  const map = useMap();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const taxisRef = useRef(taxis);
  taxisRef.current = taxis;

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const size = map.getSize();
    canvas.width = size.x;
    canvas.height = size.y;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, size.x, size.y);

    for (const taxi of taxisRef.current) {
      const pt = map.latLngToContainerPoint([taxi.lat, taxi.lng]);
      if (pt.x < -3 || pt.x > size.x + 3 || pt.y < -3 || pt.y > size.y + 3) continue;
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, 2, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(34,197,94,0.72)';
      ctx.fill();
    }
  }, [map]);

  useEffect(() => {
    const container = map.getContainer();
    const canvas = document.createElement('canvas');
    canvas.style.cssText = 'position:absolute;top:0;left:0;pointer-events:none;';
    canvas.style.zIndex = '450';
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
