import type { Forecast24hData, WeatherIntensity } from '../types';

const INTENSITY_COLOR: Record<WeatherIntensity, string> = {
  clear:    '#06b6d4',
  drizzle:  '#38bdf8',
  moderate: '#6366f1',
  heavy:    '#a855f7',
  storm:    '#ec4899',
};

const ICON_PATHS: Record<WeatherIntensity, React.ReactNode> = {
  clear: (
    <>
      <circle cx="12" cy="12" r="4" />
      <line x1="12" y1="2"     x2="12" y2="5"     />
      <line x1="12" y1="19"    x2="12" y2="22"    />
      <line x1="2"  y1="12"    x2="5"  y2="12"    />
      <line x1="19" y1="12"    x2="22" y2="12"    />
      <line x1="4.22"  y1="4.22"  x2="6.34"  y2="6.34"  />
      <line x1="17.66" y1="17.66" x2="19.78" y2="19.78" />
      <line x1="4.22"  y1="19.78" x2="6.34"  y2="17.66" />
      <line x1="17.66" y1="6.34"  x2="19.78" y2="4.22"  />
    </>
  ),
  drizzle: (
    <>
      <path d="M18 10a6 6 0 0 0-11.8-1.5A4 4 0 1 0 6 17h12a4 4 0 0 0 0-8z" />
      <line x1="9"  y1="19" x2="9"  y2="22" strokeDasharray="1 2" />
      <line x1="14" y1="19" x2="14" y2="22" strokeDasharray="1 2" />
    </>
  ),
  moderate: (
    <>
      <path d="M18 10a6 6 0 0 0-11.8-1.5A4 4 0 1 0 6 17h12a4 4 0 0 0 0-8z" />
      <line x1="8"  y1="19" x2="7"  y2="22" />
      <line x1="12" y1="19" x2="11" y2="22" />
      <line x1="16" y1="19" x2="15" y2="22" />
    </>
  ),
  heavy: (
    <>
      <path d="M20 17.58A5 5 0 0 0 18 8h-1.26A8 8 0 1 0 4 16.25" />
      <line x1="8"  y1="19" x2="7"  y2="22" />
      <line x1="11" y1="19" x2="10" y2="22" />
      <line x1="14" y1="19" x2="13" y2="22" />
      <line x1="17" y1="19" x2="16" y2="22" />
    </>
  ),
  storm: (
    <>
      <path d="M19 16.9A5 5 0 0 0 18 7h-1.26a8 8 0 1 0-11.62 9" />
      <polyline points="13 11 9 17 15 17 11 23" />
    </>
  ),
};

function WeatherIcon({
  intensity, color, size = 22, pulse = false,
}: {
  intensity: WeatherIntensity; color: string; size?: number; pulse?: boolean;
}) {
  return (
    <svg
      width={size} height={size} viewBox="0 0 24 24"
      stroke={color} strokeWidth={1.5} fill="none"
      strokeLinecap="round" strokeLinejoin="round"
      className={pulse ? 'animate-pulse' : undefined}
      style={{ filter: `drop-shadow(0 0 4px ${color}88)`, flexShrink: 0 }}
    >
      {ICON_PATHS[intensity]}
    </svg>
  );
}

// N / S / E / W / C dot order — matches the 5 Singapore planning regions
const REGION_ORDER = ['north', 'south', 'east', 'west', 'central'];
const REGION_ABBR  = ['N', 'S', 'E', 'W', 'C'];

interface Props {
  data: Forecast24hData;
}

export default function Forecast24hTimeline({ data }: Props) {
  const { general, periods } = data;

  const tempStr = general.temp_low || general.temp_high
    ? `${general.temp_low}–${general.temp_high}°C`
    : null;
  const rhStr = general.rh_low || general.rh_high
    ? `${general.rh_low}–${general.rh_high}%RH`
    : null;

  return (
    <div className="glass p-3 flex-1 pointer-events-auto">
      {/* ── Header ── */}
      <div className="flex items-center justify-between mb-3">
        <h3
          className="font-black tracking-[0.18em] uppercase flex items-center gap-1"
          style={{ fontSize: 9, color: 'rgba(255,255,255,0.45)' }}
        >
          {/* Calendar micro-icon */}
          <svg
            width={13} height={13} viewBox="0 0 24 24"
            stroke="rgba(6,182,212,0.55)" strokeWidth={1.5} fill="none"
            strokeLinecap="round" strokeLinejoin="round"
            style={{ flexShrink: 0 }}
          >
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
            <line x1="16" y1="2" x2="16" y2="6" />
            <line x1="8"  y1="2" x2="8"  y2="6" />
            <line x1="3"  y1="10" x2="21" y2="10" />
          </svg>
          24-Hour Forecast
        </h3>
        {(tempStr || rhStr) && (
          <span
            className="font-semibold tracking-wide"
            style={{ fontSize: 8, color: 'rgba(255,255,255,0.28)' }}
          >
            {[tempStr, rhStr].filter(Boolean).join('  ')}
          </span>
        )}
      </div>

      {periods.length === 0 ? (
        <p style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)', fontStyle: 'italic' }}>
          Forecast loading…
        </p>
      ) : (
        <div className="flex items-start justify-between gap-1">
          {periods.map((period, i) => {
            const col = INTENSITY_COLOR[period.dominant_intensity];
            return (
              <div key={`${period.time_text}-${i}`} className="flex items-start gap-1">
                <div className="text-center flex flex-col items-center gap-1">
                  {/* Weather icon */}
                  <WeatherIcon
                    intensity={period.dominant_intensity}
                    color={col}
                    size={22}
                    pulse={period.dominant_intensity === 'storm'}
                  />

                  {/* Time band label */}
                  <div
                    className="font-semibold tracking-wide"
                    style={{ fontSize: 9, color: 'rgba(255,255,255,0.45)' }}
                  >
                    {period.time_text}
                  </div>

                  {/* Dominant forecast label */}
                  <div
                    className="font-black tracking-wide"
                    style={{ fontSize: 11, color: col, textShadow: `0 0 8px ${col}80` }}
                  >
                    {period.dominant_forecast}
                  </div>

                  {/* Region dots: N S E W C */}
                  <div className="flex items-center gap-0.5 mt-0.5">
                    {REGION_ORDER.map((reg, ri) => {
                      const intensity = period.regions[reg] ?? 'clear';
                      const dotCol = INTENSITY_COLOR[intensity];
                      return (
                        <div
                          key={reg}
                          title={`${REGION_ABBR[ri]}: ${intensity}`}
                          className="rounded-full"
                          style={{
                            width: 5, height: 5,
                            background: dotCol,
                            boxShadow: `0 0 3px ${dotCol}80`,
                          }}
                        />
                      );
                    })}
                  </div>
                </div>

                {i < periods.length - 1 && (
                  <div
                    className="font-black"
                    style={{
                      fontSize: 18,
                      color:    INTENSITY_COLOR[periods[i + 1].dominant_intensity],
                      opacity:  0.7,
                      marginTop: 14,
                    }}
                  >
                    →
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
