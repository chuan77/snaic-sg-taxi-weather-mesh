import { useState, useEffect } from 'react';

export interface AreaPrediction {
  area: string;
  now: number;
  in_30min: number;
  in_1h: number;
  in_2h: number;
}

export interface PatternData {
  generated_at: string;
  sufficient_data: boolean;
  val_mae?: number;
  val_r2?: number;
  train_val_mae_gap?: number;
  predictions: AreaPrediction[];
  low_availability_hours: Record<string, number[]>;
}

const FALLBACK: PatternData = {
  generated_at: '',
  sufficient_data: false,
  predictions: [],
  low_availability_hours: {},
};

export function usePattern(): { data: PatternData; loading: boolean; error: string | null } {
  const [data, setData] = useState<PatternData>(FALLBACK);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function fetch_() {
      try {
        const res = await fetch(`/data/pattern.json?t=${Date.now()}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json: PatternData = await res.json();
        if (!cancelled) { setData(json); setError(null); }
      } catch (e) {
        if (!cancelled) setError(String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    fetch_();
    const id = setInterval(fetch_, 300_000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  return { data, loading, error };
}
