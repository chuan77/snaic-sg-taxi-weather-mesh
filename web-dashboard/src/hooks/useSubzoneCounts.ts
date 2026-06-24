import { useState, useEffect, useMemo } from 'react';
import type { TaxiPoint, SubzoneCollection } from '../types';

// Ray-casting point-in-polygon for a single ring (GeoJSON coords: [lng, lat])
function pointInRing(px: number, py: number, ring: number[][]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if (yi > py !== yj > py && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

// Returns true if point [lng, lat] is inside the GeoJSON geometry
function pointInGeometry(
  lng: number,
  lat: number,
  geometry: SubzoneCollection['features'][0]['geometry']
): boolean {
  if (geometry.type === 'Polygon') {
    const rings = geometry.coordinates as number[][][];
    // First ring is outer boundary; subsequent rings are holes
    if (!pointInRing(lng, lat, rings[0])) return false;
    for (let r = 1; r < rings.length; r++) {
      if (pointInRing(lng, lat, rings[r])) return false; // inside a hole
    }
    return true;
  }
  if (geometry.type === 'MultiPolygon') {
    const polys = geometry.coordinates as number[][][][];
    for (const rings of polys) {
      if (pointInRing(lng, lat, rings[0])) {
        let inHole = false;
        for (let r = 1; r < rings.length; r++) {
          if (pointInRing(lng, lat, rings[r])) { inHole = true; break; }
        }
        if (!inHole) return true;
      }
    }
  }
  return false;
}

export function useSubzoneCounts(taxis: TaxiPoint[]) {
  const [geoJson, setGeoJson] = useState<SubzoneCollection | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/sg_subzones.geojson')
      .then(r => r.json())
      .then((data: SubzoneCollection) => { setGeoJson(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const { counts, maxCount } = useMemo(() => {
    if (!geoJson || taxis.length === 0) return { counts: new Map<string, number>(), maxCount: 0 };

    const counts = new Map<string, number>();
    for (const f of geoJson.features) {
      counts.set(f.properties.SUBZONE_N, 0);
    }

    for (const taxi of taxis) {
      for (const feature of geoJson.features) {
        if (pointInGeometry(taxi.lng, taxi.lat, feature.geometry)) {
          const key = feature.properties.SUBZONE_N;
          counts.set(key, (counts.get(key) ?? 0) + 1);
          break; // subzones don't overlap — stop after first match
        }
      }
    }

    const maxCount = Math.max(0, ...counts.values());
    return { counts, maxCount };
  }, [geoJson, taxis]);

  return { counts, maxCount, geoJson, loading };
}
