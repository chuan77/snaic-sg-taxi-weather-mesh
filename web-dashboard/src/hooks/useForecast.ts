import { useState, useEffect } from 'react';
import type { DemandForecastData } from '../types';

const FALLBACK: DemandForecastData = {
  generated_at: '',
  horizon_minutes: 30,
  sufficient_data: false,
  model_mae: null,
  zones: [],
};
const POLL_MS = 300_000;

export function useForecast() {
  const [data, setData] = useState<DemandForecastData>(FALLBACK);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;

    async function fetchForecast() {
      try {
        const res = await fetch(`/data/forecast.json?t=${Date.now()}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json: DemandForecastData = await res.json();
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
