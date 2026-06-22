import { useState, useEffect } from 'react';
import type { ClustersData } from '../types';

const FALLBACK: ClustersData = { updated_at: '', snapshot_timestamp: '', cluster_count: 0, silhouette_score: null, clusters: [] };
const POLL_MS = 300_000;

export function useClusters() {
  const [data, setData] = useState<ClustersData>(FALLBACK);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;

    async function fetchClusters() {
      try {
        const res = await fetch(`/data/clusters.json?t=${Date.now()}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json: ClustersData = await res.json();
        if (alive) { setData(json); setError(null); }
      } catch (err) {
        if (alive) setError(String(err));
      } finally {
        if (alive) setLoading(false);
      }
    }

    fetchClusters();
    const timer = setInterval(fetchClusters, POLL_MS);
    return () => { alive = false; clearInterval(timer); };
  }, []);

  return { data, loading, error };
}
