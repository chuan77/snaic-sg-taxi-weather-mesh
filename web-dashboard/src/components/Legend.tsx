const WEATHER_LEVELS = [
  { label: 'Drizzle',       color: '#38bdf8' },
  { label: 'Moderate Rain', color: '#6366f1' },
  { label: 'Heavy Rain',    color: '#a855f7' },
  { label: 'Storm',         color: '#ec4899' },
];

const DEMAND_LEVELS = [
  { label: 'Low',    color: '#00b4ff' },
  { label: 'Medium', color: '#ffe000' },
  { label: 'High',   color: '#ff6200' },
  { label: 'Peak',   color: '#ff0000' },
];

const SUPPLY_GAP_LEVELS = [
  { label: 'Adequate',  color: '#00b4ff' },
  { label: 'Tight',     color: '#ffe000' },
  { label: 'Short',     color: '#ff6200' },
  { label: 'Critical',  color: '#ff0000' },
];

interface Props {
  mode?: 'map' | 'heatmap';
  invert?: boolean;
}

export default function Legend({ mode = 'map', invert = false }: Props) {
  const isHeat = mode === 'heatmap';
  const levels = isHeat ? (invert ? SUPPLY_GAP_LEVELS : DEMAND_LEVELS) : WEATHER_LEVELS;
  const gradient = isHeat
    ? 'linear-gradient(to right, #00b4ff, #ffe000, #ff6200, #ff0000)'
    : 'linear-gradient(to right, #38bdf8, #6366f1, #a855f7, #ec4899)';
  const glow = isHeat
    ? 'rgba(255, 98, 0, 0.35)'
    : 'rgba(168, 85, 247, 0.35)';
  const title = isHeat ? (invert ? 'Supply Gap' : 'Demand Density') : 'Precipitation';

  return (
    <div
      className="absolute top-3 right-3 glass p-3"
      style={{ zIndex: 1001, width: 248, pointerEvents: 'auto' }}
    >
      <h3
        className="font-black tracking-[0.22em] uppercase mb-2.5"
        style={{ fontSize: 10, color: 'rgba(255,255,255,0.55)' }}
      >
        {title}
      </h3>

      <div
        className="h-2.5 rounded-full mb-2"
        style={{ background: gradient, boxShadow: `0 0 8px ${glow}` }}
      />

      <div className="flex justify-between">
        {levels.map(({ label, color }) => (
          <span
            key={label}
            className="font-bold uppercase"
            style={{ fontSize: 8.5, color, letterSpacing: '0.06em' }}
          >
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}
