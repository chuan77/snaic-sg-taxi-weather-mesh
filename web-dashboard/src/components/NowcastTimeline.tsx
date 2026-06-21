import type { NowcastStep, WeatherIntensity } from '../types';

const INTENSITY_COLOR: Record<WeatherIntensity, string> = {
  clear:    '#06b6d4',
  drizzle:  '#38bdf8',
  moderate: '#6366f1',
  heavy:    '#a855f7',
  storm:    '#ec4899',
};

interface Props {
  steps: NowcastStep[];
  /** e.g. "11.00 am to 1.00 pm" from valid_period.text */
  validPeriodText?: string;
}

export default function NowcastTimeline({ steps, validPeriodText }: Props) {
  return (
    <div className="glass p-3 flex-1 pointer-events-auto">
      <div className="flex items-center justify-between mb-3">
        <h3
          className="font-black tracking-[0.18em] uppercase"
          style={{ fontSize: 9, color: 'rgba(255,255,255,0.45)' }}
        >
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
              <div className="text-center">
                <div
                  className="font-semibold tracking-wide mb-1"
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
