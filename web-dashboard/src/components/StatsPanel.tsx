export default function StatsPanel() {
  return (
    <div className="glass p-3 flex-1 pointer-events-auto">
      <div className="flex h-full gap-0">

        {/* Stat 1: Active Taxis */}
        <div className="flex flex-col justify-center flex-1">
          <div
            className="font-black uppercase tracking-[0.16em] mb-1"
            style={{ fontSize: 9, color: 'rgba(255,255,255,0.38)' }}
          >
            Active Taxis (SG)
          </div>
          <div
            className="font-black tabular-nums leading-none"
            style={{ fontSize: 30, color: '#fff', textShadow: '0 0 14px rgba(6,182,212,0.45)' }}
          >
            14,830
          </div>
        </div>

        <div className="w-px mx-3 self-stretch" style={{ background: 'rgba(255,255,255,0.08)' }} />

        {/* Stat 2: Wait Time */}
        <div className="flex flex-col justify-center flex-1">
          <div
            className="font-black uppercase tracking-[0.16em] mb-1"
            style={{ fontSize: 9, color: 'rgba(255,255,255,0.38)' }}
          >
            Ave. Wait Time
          </div>
          <div className="flex items-baseline gap-1">
            <span
              className="font-black tabular-nums leading-none"
              style={{ fontSize: 30, color: '#fff', textShadow: '0 0 14px rgba(168,85,247,0.45)' }}
            >
              12
            </span>
            <span
              className="font-bold"
              style={{ fontSize: 14, color: '#c084fc' }}
            >
              min
            </span>
          </div>
          <div
            className="font-semibold mt-0.5"
            style={{ fontSize: 9, color: '#a855f7' }}
          >
            Heavy Rain Zones
          </div>
        </div>

      </div>
    </div>
  );
}
