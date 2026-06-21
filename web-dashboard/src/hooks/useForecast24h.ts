import { useState, useEffect } from 'react';
import type { Forecast24hData } from '../types';

const FALLBACK: Forecast24hData = {
  updated_at: '',
  valid_period: { start: '', end: '' },
  general: { forecast: '', intensity: 'clear', temp_low: 0, temp_high: 0, rh_low: 0, rh_high: 0 },
  periods: [],
};
const POLL_MS = 300_000;

export function useForecast24h() {
  const [data, setData] = useState<Forecast24hData>(FALLBACK);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;

    async function fetchForecast() {
      try {
        const res = await fetch(`/data/forecast24h.json?t=${Date.now()}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json: Forecast24hData = await res.json();
        if (alive) { setData(json); setError(null); }
      } catch (err) {
        if (alive) setError(String(err));
      } finally {
        if (alive) setLoading(false);
      }
    }

    fetchForecast();
    const timer = setInterval(fetchForecast, POLL_MS);
    return () => { alive = false; clearInterval(timer); };
  }, []);

  return { data, loading, error };
}
