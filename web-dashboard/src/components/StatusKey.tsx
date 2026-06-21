function CarIcon({ color }: { color: string }) {
  return (
    <svg width="22" height="14" viewBox="0 0 22 15" xmlns="http://www.w3.org/2000/svg">
      <rect x="1" y="5" width="20" height="8" rx="2.5" fill={color} opacity="0.92" />
      <path
        d="M4 5 L6.5 1.5 Q7.2 0.5 8.5 0.5 L13.5 0.5 Q14.8 0.5 15.5 1.5 L18 5 Z"
        fill={color}
        opacity="0.85"
      />
      <rect x="7" y="1.2" width="8" height="3.8" rx="1" fill="rgba(180,230,255,0.2)" />
      <circle cx="5.5"  cy="13.5" r="1.8" fill={color} opacity="0.8" />
      <circle cx="16.5" cy="13.5" r="1.8" fill={color} opacity="0.8" />
    </svg>
  );
}

export default function StatusKey() {
  return (
    <div
      className="absolute glass p-3"
      style={{ top: '50%', right: '12px', transform: 'translateY(-50%)', zIndex: 1001, width: 130 }}
    >
      <h3
        className="font-black tracking-[0.2em] uppercase mb-2.5"
        style={{ fontSize: 9, color: 'rgba(255,255,255,0.45)' }}
      >
        Taxi Status
      </h3>
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <div style={{ filter: 'drop-shadow(0 0 4px rgba(34,197,94,0.6))' }}>
            <CarIcon color="#22c55e" />
          </div>
          <span className="font-semibold tracking-wide" style={{ fontSize: 11, color: 'rgba(255,255,255,0.75)' }}>
            Available
          </span>
        </div>
        <div className="flex items-center gap-2 opacity-35">
          <div>
            <CarIcon color="#eab308" />
          </div>
          <span className="font-semibold tracking-wide" style={{ fontSize: 11, color: 'rgba(255,255,255,0.75)' }}>
            Hired
          </span>
        </div>
        <div className="flex items-center gap-2 opacity-35">
          <div>
            <CarIcon color="#3b82f6" />
          </div>
          <span className="font-semibold tracking-wide" style={{ fontSize: 11, color: 'rgba(255,255,255,0.75)' }}>
            Pre-booked
          </span>
        </div>
        <div
          className="mt-1 pt-1.5"
          style={{ borderTop: '1px solid rgba(255,255,255,0.08)', fontSize: 8, color: 'rgba(255,255,255,0.3)', lineHeight: 1.4 }}
        >
          Live data: available only.<br />Hired/pre-booked not in API.
        </div>
      </div>
    </div>
  );
}
