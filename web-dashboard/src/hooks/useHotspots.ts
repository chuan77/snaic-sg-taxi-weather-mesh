import { useState, useEffect } from 'react';
import type { HotspotsData } from '../types';

const FALLBACK: HotspotsData = {
  updated_at: '',
  total_taxis_online: 0,
  snapshot_timestamp: '',
  fleet_coverage_score: null,
  hotspots: [
    { id: 'h1', name: 'Marina Bay / CBD', level: 'high',   taxi_count: 0, lat: 1.2897, lng: 103.8501, sdi: 0, sdi_label: 'Shortage' },
    { id: 'h2', name: 'Changi Airport',   level: 'medium', taxi_count: 0, lat: 1.3592, lng: 103.9894, sdi: 0, sdi_label: 'Shortage' },
    { id: 'h3', name: 'Orchard Road',     level: 'high',   taxi_count: 0, lat: 1.3048, lng: 103.8318, sdi: 0, sdi_label: 'Shortage' },
    { id: 'h4', name: 'Jurong East',      level: 'low',    taxi_count: 0, lat: 1.3330, lng: 103.7436, sdi: 0, sdi_label: 'Shortage' },
    { id: 'h5', name: 'Woodlands',        level: 'low',    taxi_count: 0, lat: 1.4382, lng: 103.7891, sdi: 0, sdi_label: 'Shortage' },
    { id: 'h6', name: 'Tampines',         level: 'medium', taxi_count: 0, lat: 1.3530, lng: 103.9434, sdi: 0, sdi_label: 'Shortage' },
  ],
};

const POLL_MS = 300_000;

export function useHotspots() {
  const [data, setData] = useState<HotspotsData>(FALLBACK);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;

    async function fetchHotspots() {
      try {
        const res = await fetch(`/data/hotspots.json?t=${Date.now()}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json: HotspotsData = await res.json();
        if (alive) { setData(json); setError(null); }
      } catch (err) {
        if (alive) setError(String(err));
      } finally {
        if (alive) setLoading(false);
      }
    }

    fetchHotspots();
    const timer = setInterval(fetchHotspots, POLL_MS);
    return () => { alive = false; clearInterval(timer); };
  }, []);

  return { data, loading, error };
}
