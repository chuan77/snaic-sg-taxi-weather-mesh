import { useState, useEffect } from 'react';
import type { NowcastData } from '../types';

const FALLBACK: NowcastData = {
  updated_at: '',
  valid_period: { start: '', end: '', text: 'Loading…' },
  alert: { active: false, message: 'Loading weather data…' },
  regions: { North: 'clear', South: 'clear', East: 'clear', West: 'clear', Central: 'clear' },
  areas: [],
  timeline: [
    { time: '—', label: 'Loading…', intensity: 'clear' },
    { time: '—', label: 'Loading…', intensity: 'clear' },
    { time: '—', label: 'Loading…', intensity: 'clear' },
  ],
};

/**
 * Fetches /data/nowcast.json (written by the Dagster weather_nowcast_export asset)
 * and re-polls every `pollMs` milliseconds (default 5 minutes, matching the Dagster schedule).
 */
export function useNowcast(pollMs = 300_000): { data: NowcastData; loading: boolean; error: string | null } {
  const [data, setData]       = useState<NowcastData>(FALLBACK);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchNowcast = async () => {
      try {
        // Cache-bust so stale Vite dev-server responses are avoided
        const res = await fetch(`/data/nowcast.json?t=${Date.now()}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json: NowcastData = await res.json();
        if (!cancelled) { setData(json); setError(null); }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Fetch failed');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchNowcast();
    const id = setInterval(fetchNowcast, pollMs);
    return () => { cancelled = true; clearInterval(id); };
  }, [pollMs]);

  return { data, loading, error };
}
