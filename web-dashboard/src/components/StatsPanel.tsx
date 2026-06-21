import type { WeatherIntensity } from '../types';

const INTENSITY_RANK: Record<WeatherIntensity, number> = {
  clear: 0, drizzle: 1, moderate: 2, heavy: 3, storm: 4,
};

const WAIT_CONFIG: Record<WeatherIntensity, { mins: number; label: string }> = {
  clear:    { mins: 3,  label: 'Normal Conditions' },
  drizzle:  { mins: 5,  label: 'Light Rain Zones' },
  moderate: { mins: 8,  label: 'Shower Zones' },
  heavy:    { mins: 12, label: 'Heavy Rain Zones' },
  storm:    { mins: 18, label: 'Storm Zones' },
};

interface Props {
  totalTaxis: number;
  regions: Record<string, WeatherIntensity>;
}

export default function StatsPanel({ totalTaxis, regions }: Props) {
  const dominantIntensity = (Object.values(regions) as WeatherIntensity[]).reduce<WeatherIntensity>(
    (max, cur) => (INTENSITY_RANK[cur] > INTENSITY_RANK[max] ? cur : max),
    'clear',
  );

  const { mins, label } = WAIT_CONFIG[dominantIntensity];

  return (
    <div className="glass p-3 flex-1 pointer-events-auto">
      <div className="flex h-full gap-0">

        {/* Stat 1: Active Taxis */}
        <div className="flex flex-col justify-center flex-1">
          <div
            className="font-black uppercase tracking-[0.16em] mb-1"
            style={{ fontSize: 9, color: 'rgba(255,255,255,0.38)' }}
          >
            Active Taxis (SG)
          </div>
          <div
            className="font-black tabular-nums leading-none"
            style={{ fontSize: 30, color: '#fff', textShadow: '0 0 14px rgba(6,182,212,0.45)' }}
          >
            {totalTaxis > 0 ? totalTaxis.toLocaleString() : '—'}
          </div>
        </div>

        <div className="w-px mx-3 self-stretch" style={{ background: 'rgba(255,255,255,0.08)' }} />

        {/* Stat 2: Wait Time — derived from dominant weather intensity across regions */}
        <div className="flex flex-col justify-center flex-1">
          <div
            className="font-black uppercase tracking-[0.16em] mb-1"
            style={{ fontSize: 9, color: 'rgba(255,255,255,0.38)' }}
          >
            Ave. Wait Time
          </div>
          <div className="flex items-baseline gap-1">
            <span
              className="font-black tabular-nums leading-none"
              style={{ fontSize: 30, color: '#fff', textShadow: '0 0 14px rgba(168,85,247,0.45)' }}
            >
              {mins}
            </span>
            <span
              className="font-bold"
              style={{ fontSize: 14, color: '#c084fc' }}
            >
              min
            </span>
          </div>
          <div
            className="font-semibold mt-0.5"
            style={{ fontSize: 9, color: '#a855f7' }}
          >
            {label}
          </div>
        </div>

      </div>
    </div>
  );
}
