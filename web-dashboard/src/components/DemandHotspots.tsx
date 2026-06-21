import type { HotspotEntry } from '../types';

const LEVEL_STYLE = {
  high:   { label: 'HIGH',   badge: 'PURPLE', textColor: '#e879f9', dotColor: '#a855f7' },
  medium: { label: 'MEDIUM', badge: 'BLUE',   textColor: '#38bdf8', dotColor: '#3b82f6' },
  low:    { label: 'LOW',    badge: 'CYAN',   textColor: '#06b6d4', dotColor: '#06b6d4' },
};

interface Props {
  hotspots: HotspotEntry[];
  totalTaxis?: number;
}

export default function DemandHotspots({ hotspots, totalTaxis }: Props) {
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
          const style = LEVEL_STYLE[h.level];
          return (
            <div key={h.id} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div
                  className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                  style={{
                    background: style.dotColor,
                    boxShadow: `0 0 4px ${style.dotColor}`,
                  }}
                />
                <span
                  className="font-medium"
                  style={{ fontSize: 12, color: 'rgba(255,255,255,0.8)' }}
                >
                  {h.name}
                </span>
              </div>
              <div className="flex items-center gap-1.5 flex-shrink-0">
                {h.taxi_count > 0 && (
                  <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.45)' }}>
                    {h.taxi_count}
                  </span>
                )}
                <span
                  className="font-black tracking-wide"
                  style={{ fontSize: 11, color: style.textColor }}
                >
                  {style.label}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
