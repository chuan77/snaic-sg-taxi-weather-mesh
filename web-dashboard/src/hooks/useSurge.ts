import { useState, useEffect } from 'react';
import type { SurgeData } from '../types';

const FALLBACK: SurgeData = { updated_at: '', alert_active: false, alert_message: '', zones: [] };
const POLL_MS = 300_000;

export function useSurge() {
  const [data, setData] = useState<SurgeData>(FALLBACK);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;

    async function fetchSurge() {
      try {
        const res = await fetch(`/data/surge.json?t=${Date.now()}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json: SurgeData = await res.json();
        if (alive) { setData(json); setError(null); }
      } catch (err) {
        if (alive) setError(String(err));
      } finally {
        if (alive) setLoading(false);
      }
    }

    fetchSurge();
    const timer = setInterval(fetchSurge, POLL_MS);
    return () => { alive = false; clearInterval(timer); };
  }, []);

  return { data, loading, error };
}
