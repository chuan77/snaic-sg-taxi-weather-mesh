import type { HotspotEntry, SurgeZone, ForecastZone } from '../types';

const LEVEL_STYLE = {
  high:   { dotColor: '#a855f7' },
  medium: { dotColor: '#3b82f6' },
  low:    { dotColor: '#06b6d4' },
};

const SDI_COLOR: Record<string, string> = {
  Shortage: '#ef4444',
  Tight:    '#f59e0b',
  Adequate: '#22c55e',
};

const SURGE_PULSE: Record<string, string> = {
  critical: '#ef4444',
  high:     '#f97316',
  moderate: '#eab308',
  low:      '',
};

function deltaColor(delta: number): string {
  if (delta > 3)  return '#06b6d4';  // growing — cyan
  if (delta < -3) return '#f43f5e';  // dropping — pink
  return '#f59e0b';                   // stable — amber
}

interface Props {
  hotspots: HotspotEntry[];
  totalTaxis?: number;
  surgeZones?: SurgeZone[];
  forecastZones?: ForecastZone[];
}

export default function DemandHotspots({ hotspots, totalTaxis, surgeZones = [], forecastZones = [] }: Props) {
  const surgeMap    = Object.fromEntries(surgeZones.map(z => [z.id, z]));
  const forecastMap = Object.fromEntries(forecastZones.map(z => [z.id, z]));

  return (
    <div className="glass p-3 flex-1 pointer-events-auto">
      <div className="flex items-center justify-between mb-2.5">
        <h3
          className="font-black tracking-[0.18em] uppercase"
          style={{ fontSize: 9, color: 'rgba(255,255,255,0.45)' }}
        >
          Demand Hotspots
        </h3>
        {totalTaxis !== undefined && totalTaxis > 0 && (
          <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)' }}>
            {totalTaxis.toLocaleString()} online
          </span>
        )}
      </div>

      <div className="flex flex-col gap-2">
        {hotspots.map((h) => {
          const dot   = LEVEL_STYLE[h.level].dotColor;
          const surge = surgeMap[h.id];
          const pulseColor = surge ? SURGE_PULSE[surge.alert_level] : '';
          const sdiColor   = h.sdi_label ? SDI_COLOR[h.sdi_label] ?? '#6b7280' : '#6b7280';

          const fz = forecastMap[h.id];

          return (
            <div key={h.id} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {/* Status dot — pulses red/orange on surge */}
                <div
                  className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                  style={{
                    background: pulseColor || dot,
                    boxShadow:  `0 0 ${pulseColor ? '6px' : '4px'} ${pulseColor || dot}`,
                  }}
                />
                <span
                  className="font-medium"
                  style={{ fontSize: 12, color: 'rgba(255,255,255,0.8)' }}
                >
                  {h.name}
                </span>
              </div>

              <div className="flex items-center gap-2 flex-shrink-0">
                {/* SDI badge */}
                {h.sdi !== undefined && (
                  <span
                    className="font-black tabular-nums"
                    style={{ fontSize: 10, color: sdiColor }}
                    title={`Supply-Demand Index: ${h.sdi}`}
                  >
                    {h.sdi_label}
                  </span>
                )}
                {/* Taxi count */}
                {h.taxi_count > 0 && (
                  <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)' }}>
                    {h.taxi_count}
                  </span>
                )}
                {/* 30-min prediction chip */}
                {fz && (
                  <span
                    className="font-semibold tabular-nums"
                    style={{ fontSize: 9, color: deltaColor(fz.delta) }}
                    title={`Predicted in 30 min: ${fz.predicted_count} (${fz.delta >= 0 ? '+' : ''}${fz.delta})`}
                  >
                    →{fz.predicted_count}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
