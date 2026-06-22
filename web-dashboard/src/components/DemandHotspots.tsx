import { useState } from 'react';
import type { HotspotEntry, SurgeZone, ForecastZone, PlanningAreaEntry } from '../types';

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

const ZONE_AREA: Record<string, string> = {
  h1: 'Downtown Core',
  h2: 'Changi',
  h3: 'Orchard',
  h4: 'Jurong East',
  h5: 'Woodlands',
  h6: 'Tampines',
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
  planningAreas?: PlanningAreaEntry[];
}

export default function DemandHotspots({ hotspots, totalTaxis, surgeZones = [], forecastZones = [], planningAreas = [] }: Props) {
  const surgeMap    = Object.fromEntries(surgeZones.map(z => [z.id, z]));
  const forecastMap = Object.fromEntries(forecastZones.map(z => [z.id, z]));
  const [areasOpen, setAreasOpen] = useState(false);

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
                <div>
                  <span
                    className="font-medium"
                    style={{ fontSize: 12, color: 'rgba(255,255,255,0.8)' }}
                  >
                    {h.name}
                  </span>
                  {ZONE_AREA[h.id] && (
                    <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)', display: 'block', marginTop: 1 }}>
                      {ZONE_AREA[h.id]}
                    </span>
                  )}
                </div>
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
                {/* T2-F3: Competition delta since last snapshot */}
                {h.delta_count != null && h.delta_count !== 0 && (
                  <span
                    className="font-semibold tabular-nums"
                    style={{ fontSize: 9, color: deltaColor(h.delta_count), opacity: 0.8 }}
                    title={`Taxis since last snapshot: ${h.delta_count > 0 ? '+' : ''}${h.delta_count}`}
                  >
                    {h.delta_count > 0 ? `▲${h.delta_count}` : `▼${Math.abs(h.delta_count)}`}
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

      {/* Planning areas accordion — only shown when subzones data is loaded */}
      {planningAreas.length > 0 && (
        <div style={{ borderTop: '1px solid rgba(255,255,255,0.07)', marginTop: 8 }}>
          <button
            onClick={() => setAreasOpen(v => !v)}
            style={{
              width: '100%', display: 'flex', justifyContent: 'space-between',
              alignItems: 'center', padding: '5px 0',
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'rgba(255,255,255,0.4)', fontSize: 9, letterSpacing: '0.12em',
              textTransform: 'uppercase',
            }}
          >
            <span>Planning Areas</span>
            <span>{areasOpen ? '▴' : '▾'}</span>
          </button>

          {areasOpen && (
            <div style={{ maxHeight: 160, overflowY: 'auto' }}>
              {planningAreas.slice(0, 15).map(area => {
                const pct = totalTaxis ? Math.round((area.count / totalTaxis) * 100) : 0;
                return (
                  <div key={area.name} style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    padding: '3px 0', fontSize: 10,
                  }}>
                    <span style={{ flex: 1, color: 'rgba(255,255,255,0.7)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {area.name}
                    </span>
                    <span style={{ fontSize: 8, color: 'rgba(255,255,255,0.25)', minWidth: 28, textAlign: 'right' }}>
                      {area.region.replace(' Region', '')}
                    </span>
                    <div style={{ width: 48, height: 3, background: 'rgba(255,255,255,0.08)', borderRadius: 2 }}>
                      <div style={{ width: `${Math.min(pct * 5, 100)}%`, height: '100%', background: 'rgba(6,182,212,0.6)', borderRadius: 2 }} />
                    </div>
                    <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.4)', minWidth: 22, textAlign: 'right' }}>
                      {area.count}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
