import { useState, useEffect } from 'react';
import type { SubzonesData } from '../types';

const FALLBACK: SubzonesData = {
  generated_at: '',
  total_assigned: 0,
  unassigned: 0,
  planning_areas: [],
};

export function useSubzones() {
  const [data, setData] = useState<SubzonesData>(FALLBACK);

  useEffect(() => {
    function fetchData() {
      fetch(`/data/subzones.json?t=${Date.now()}`)
        .then(r => r.ok ? r.json() : FALLBACK)
        .then(setData)
        .catch(() => {});
    }
    fetchData();
    const id = setInterval(fetchData, 300_000);
    return () => clearInterval(id);
  }, []);

  return { data };
}
