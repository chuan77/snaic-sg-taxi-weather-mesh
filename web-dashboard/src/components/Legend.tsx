const LEVELS = [
  { label: 'Drizzle',       color: '#38bdf8' },
  { label: 'Moderate Rain', color: '#6366f1' },
  { label: 'Heavy Rain',    color: '#a855f7' },
  { label: 'Storm',         color: '#ec4899' },
];

export default function Legend() {
  return (
    <div
      className="absolute top-3 right-3 glass p-3"
      style={{ zIndex: 1001, width: 248, pointerEvents: 'auto' }}
    >
      <h3
        className="font-black tracking-[0.22em] uppercase mb-2.5"
        style={{ fontSize: 10, color: 'rgba(255,255,255,0.55)' }}
      >
        Legend
      </h3>

      {/* Gradient bar */}
      <div
        className="h-2.5 rounded-full mb-2"
        style={{
          background: 'linear-gradient(to right, #38bdf8, #6366f1, #a855f7, #ec4899)',
          boxShadow: '0 0 8px rgba(168, 85, 247, 0.35)',
        }}
      />

      {/* Labels */}
      <div className="flex justify-between">
        {LEVELS.map(({ label, color }) => (
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
