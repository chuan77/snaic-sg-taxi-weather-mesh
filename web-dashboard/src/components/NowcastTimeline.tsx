import type { NowcastStep, WeatherIntensity } from '../types';

const INTENSITY_COLOR: Record<WeatherIntensity, string> = {
  clear:    '#06b6d4',
  drizzle:  '#38bdf8',
  moderate: '#6366f1',
  heavy:    '#a855f7',
  storm:    '#ec4899',
};

// Inline SVG paths — thin-stroke, 24×24 viewBox, no external dependency
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

interface Props {
  steps: NowcastStep[];
  validPeriodText?: string;
}

export default function NowcastTimeline({ steps, validPeriodText }: Props) {
  return (
    <div className="glass p-3 flex-1 pointer-events-auto">
      <div className="flex items-center justify-between mb-3">
        <h3
          className="font-black tracking-[0.18em] uppercase flex items-center gap-1"
          style={{ fontSize: 9, color: 'rgba(255,255,255,0.45)' }}
        >
          {/* Header cloud micro-icon */}
          <svg
            width={13} height={13} viewBox="0 0 24 24"
            stroke="rgba(6,182,212,0.55)" strokeWidth={1.5} fill="none"
            strokeLinecap="round" strokeLinejoin="round"
            style={{ flexShrink: 0 }}
          >
            <path d="M18 10a6 6 0 0 0-11.8-1.5A4 4 0 1 0 6 17h12a4 4 0 0 0 0-8z" />
          </svg>
          2-Hour NEA Precipitation Nowcast
        </h3>
        {validPeriodText && (
          <span
            className="font-semibold tracking-wide"
            style={{ fontSize: 8, color: 'rgba(255,255,255,0.28)' }}
          >
            {validPeriodText}
          </span>
        )}
      </div>

      <div className="flex items-center justify-between gap-1">
        {steps.map((step, i) => {
          const col = INTENSITY_COLOR[step.intensity];
          return (
            <div key={`${step.time}-${i}`} className="flex items-center gap-1">
              <div className="text-center flex flex-col items-center gap-1">
                {/* Weather icon — coloured, glowing, storm pulses */}
                <WeatherIcon
                  intensity={step.intensity}
                  color={col}
                  size={22}
                  pulse={step.intensity === 'storm'}
                />
                <div
                  className="font-semibold tracking-wide"
                  style={{ fontSize: 9, color: 'rgba(255,255,255,0.45)' }}
                >
                  {step.time}
                </div>
                <div
                  className="font-black tracking-wide"
                  style={{ fontSize: 14, color: col, textShadow: `0 0 10px ${col}80` }}
                >
                  {step.label}
                </div>
              </div>

              {i < steps.length - 1 && (
                <div
                  className="font-black"
                  style={{
                    fontSize: 18,
                    color:    INTENSITY_COLOR[steps[i + 1].intensity],
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
    </div>
  );
}
