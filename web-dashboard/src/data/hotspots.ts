import type { Hotspot, NowcastStep } from '../types';

export const HOTSPOTS: Hotspot[] = [
  { id: 'h1', name: 'Marina Bay Sands', level: 'high',   lat: 1.2834, lng: 103.8607 },
  { id: 'h2', name: 'Changi Airport T3', level: 'medium', lat: 1.3592, lng: 103.9894 },
  { id: 'h3', name: 'Orchard Road',      level: 'high',   lat: 1.3048, lng: 103.8318 },
];

export const NOWCAST_STEPS: NowcastStep[] = [
  { time: '10:45 AM', label: 'Drizzle',  intensity: 'drizzle'  },
  { time: '11:15 AM', label: 'Moderate', intensity: 'moderate' },
  { time: '11:45 AM', label: 'Heavy',    intensity: 'heavy'    },
];
