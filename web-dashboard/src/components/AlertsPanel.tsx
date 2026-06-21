import type { SurgeData, NowcastAlert } from '../types';

const LEVEL_COLOR: Record<string, string> = {
  critical: '#ec4899',
  high:     '#f97316',
  moderate: '#f59e0b',
  low:      '#38bdf8',
};

const LEVEL_ORDER: Record<string, number> = {
  critical: 0, high: 1, moderate: 2, low: 3,
};

function formatTime(iso: string): string {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleTimeString('en-SG', { hour: '2-digit', minute: '2-digit' });
  } catch {
    return iso;
  }
}

interface Props {
  surge: SurgeData;
  nowcastAlert: NowcastAlert;
}

export default function AlertsPanel({ surge, nowcastAlert }: Props) {
  const updatedAt = surge.updated_at ? formatTime(surge.updated_at) : '—';

  const sortedZones = [...surge.zones].sort(
    (a, b) => (LEVEL_ORDER[a.alert_level] ?? 9) - (LEVEL_ORDER[b.alert_level] ?? 9)
  );

  return (
    <div
      className="absolute left-3 right-3 glass pointer-events-auto"
      style={{ bottom: '60px', zIndex: 1001, maxHeight: '70vh', overflowY: 'auto' }}
    >
      {/* ── Panel header ──────────────────────────────────────────────── */}
      <div
        className="flex items-center justify-between px-4 py-3"
        style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}
      >
        <div className="flex items-center gap-2">
          {/* Bell icon */}
          <svg width={14} height={14} viewBox="0 0 24 24"
            stroke="rgba(34,211,238,0.75)" strokeWidth={1.5} fill="none"
            strokeLinecap="round" strokeLinejoin="round"
          >
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.73 21a2 2 0 0 1-3.46 0" />
          </svg>
          <span
            className="font-black tracking-[0.22em] uppercase"
            style={{ fontSize: 10, color: 'rgba(255,255,255,0.55)' }}
          >
            Live Alerts
          </span>
        </div>
        <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.28)', fontWeight: 600 }}>
          updated {updatedAt}
        </span>
      </div>

      <div className="px-4 py-3 flex flex-col gap-4">

        {/* ── AI Demand Forecast ────────────────────────────────────────── */}
        <section>
          <div className="flex items-center gap-1.5 mb-2">
            {/* Lightning bolt */}
            <svg width={11} height={11} viewBox="0 0 24 24"
              stroke="#f59e0b" strokeWidth={2} fill="none"
              strokeLinecap="round" strokeLinejoin="round"
            >
              <polyline points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
            </svg>
            <span
              className="font-black tracking-[0.2em] uppercase"
              style={{ fontSize: 9, color: 'rgba(255,255,255,0.45)' }}
            >
              AI Demand Forecast
            </span>
            <span style={{ fontSize: 8, color: 'rgba(255,255,255,0.22)', marginLeft: 4 }}>
              · LMStudio
            </span>
          </div>

          {surge.alert_active && surge.alert_message ? (
            <div
              className="rounded px-3 py-2.5"
              style={{
                background: 'rgba(245,158,11,0.10)',
                border: '1px solid rgba(245,158,11,0.30)',
              }}
            >
              <p style={{ fontSize: 12, color: '#fcd34d', lineHeight: 1.5, margin: 0 }}>
                {surge.alert_message}
              </p>
            </div>
          ) : (
            <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.28)', fontStyle: 'italic' }}>
              No surge conditions detected.
            </p>
          )}
        </section>

        {/* ── Zone Demand Status ────────────────────────────────────────── */}
        {sortedZones.length > 0 && (
          <section>
            <span
              className="font-black tracking-[0.2em] uppercase block mb-2"
              style={{ fontSize: 9, color: 'rgba(255,255,255,0.45)' }}
            >
              Zone Demand Status
            </span>

            <div className="flex flex-col gap-2">
              {sortedZones.map(zone => {
                const col = LEVEL_COLOR[zone.alert_level] ?? '#94a3b8';
                return (
                  <div key={zone.id}>
                    <div className="flex items-center gap-2">
                      {/* Level dot */}
                      <div
                        className="rounded-full flex-shrink-0"
                        style={{
                          width: 7, height: 7,
                          background: col,
                          boxShadow: `0 0 6px ${col}80`,
                        }}
                      />

                      {/* Zone name + forecast */}
                      <div className="flex-1 min-w-0">
                        <span
                          className="font-bold block truncate"
                          style={{ fontSize: 11, color: 'rgba(255,255,255,0.80)' }}
                        >
                          {zone.name}
                        </span>
                        <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.35)' }}>
                          {zone.forecast}
                        </span>
                      </div>

                      {/* Alert level badge */}
                      <span
                        className="font-black tracking-wide uppercase flex-shrink-0 rounded px-1.5 py-0.5"
                        style={{
                          fontSize: 8,
                          color: col,
                          background: `${col}18`,
                          border: `1px solid ${col}40`,
                        }}
                      >
                        {zone.alert_level}
                      </span>

                      {/* Score */}
                      <span
                        className="font-black flex-shrink-0 tabular-nums"
                        style={{ fontSize: 11, color: col, minWidth: 24, textAlign: 'right' }}
                      >
                        {zone.surge_score}
                      </span>
                    </div>

                    {/* Score progress bar */}
                    <div
                      className="rounded-full mt-1"
                      style={{
                        height: 3,
                        background: 'rgba(255,255,255,0.07)',
                        marginLeft: 15,
                      }}
                    >
                      <div
                        className="rounded-full h-full"
                        style={{
                          width: `${zone.surge_score}%`,
                          background: col,
                          boxShadow: `0 0 4px ${col}60`,
                          transition: 'width 0.4s ease',
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* ── NEA Weather Advisory ─────────────────────────────────────── */}
        <section>
          <div className="flex items-center gap-1.5 mb-2">
            {/* Info circle */}
            <svg width={11} height={11} viewBox="0 0 24 24"
              stroke={nowcastAlert.active ? '#7dd3fc' : 'rgba(255,255,255,0.30)'}
              strokeWidth={2} fill="none"
              strokeLinecap="round" strokeLinejoin="round"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span
              className="font-black tracking-[0.2em] uppercase"
              style={{ fontSize: 9, color: 'rgba(255,255,255,0.45)' }}
            >
              NEA Weather Advisory
            </span>
          </div>

          {nowcastAlert.active && nowcastAlert.message ? (
            <div
              className="rounded px-3 py-2.5"
              style={{
                background: 'rgba(14,165,233,0.08)',
                border: '1px solid rgba(14,165,233,0.25)',
              }}
            >
              <p style={{ fontSize: 12, color: '#bae6fd', lineHeight: 1.5, margin: 0 }}>
                {nowcastAlert.message}
              </p>
            </div>
          ) : (
            <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.28)', fontStyle: 'italic' }}>
              All clear — no active NEA advisory.
            </p>
          )}
        </section>

      </div>
    </div>
  );
}
