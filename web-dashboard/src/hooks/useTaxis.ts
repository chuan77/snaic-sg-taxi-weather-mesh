import { useState, useEffect } from 'react';
import type { TaxisData } from '../types';

const FALLBACK: TaxisData = { updated_at: '', snapshot_timestamp: '', total: 0, taxis: [] };
const POLL_MS = 300_000;

export function useTaxis() {
  const [data, setData] = useState<TaxisData>(FALLBACK);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;

    async function fetchTaxis() {
      try {
        const res = await fetch(`/data/taxis.json?t=${Date.now()}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json: TaxisData = await res.json();
        if (alive) { setData(json); setError(null); }
      } catch (err) {
        if (alive) setError(String(err));
      } finally {
        if (alive) setLoading(false);
      }
    }

    fetchTaxis();
    const timer = setInterval(fetchTaxis, POLL_MS);
    return () => { alive = false; clearInterval(timer); };
  }, []);

  return { data, loading, error };
}
