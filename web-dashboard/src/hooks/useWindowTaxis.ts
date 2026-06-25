import { useState, useEffect } from 'react';
import type { TaxiPoint } from '../types';

interface WindowTaxisData {
  total: number;
  taxis: TaxiPoint[];
}

const EMPTY: WindowTaxisData = { total: 0, taxis: [] };
const POLL_MS = 5 * 60 * 1000;

export function useWindowTaxis(windowMinutes: 15 | 30) {
  const [data, setData] = useState<WindowTaxisData>(EMPTY);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const url = `/data/taxis_window_${windowMinutes}.json`;
    const load = () =>
      fetch(url)
        .then(r => r.json())
        .then((d: WindowTaxisData) => {
          if (active) { setData(d); setLoading(false); }
        })
        .catch(() => { if (active) setLoading(false); });

    setLoading(true);
    load();
    const id = setInterval(load, POLL_MS);
    return () => { active = false; clearInterval(id); };
  }, [windowMinutes]);

  return { data, loading };
}
