const TABS = [
  { id: 'map',    icon: '🗺️', label: 'Map View'       },
  { id: 'demand', icon: '🔥', label: 'Demand Heatmap' },
  { id: 'cluster', icon: '🏘️', label: 'Taxi Cluster'   },
  { id: 'alerts', icon: '🔔', label: 'Alerts'          },
];

const LINKS = [
  { label: 'WEATHER.GOV.SG NOWCAST', href: 'https://www.weather.gov.sg' },
  { label: 'NEA RAIN AREAS',         href: 'https://www.nea.gov.sg'     },
  { label: 'BOOK CDG TAXI',          href: '#'                           },
];

interface Props {
  activeTab: string;
  onTabChange: (id: string) => void;
}

export default function BottomNav({ activeTab, onTabChange }: Props) {
  return (
    <div
      className="absolute bottom-0 left-0 right-0"
      style={{
        height: 56,
        background: 'rgba(0, 6, 18, 0.88)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        borderTop: '1px solid rgba(255,255,255,0.07)',
        zIndex: 1002,
        display: 'flex',
        alignItems: 'center',
        paddingLeft: 12,
        paddingRight: 16,
        gap: 0,
      }}
    >
      {/* ── Tabs ──────────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-0 flex-shrink-0">
        {TABS.map((tab) => {
          const isActive = tab.id === activeTab;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className="relative flex items-center gap-1.5 px-4 h-14 font-bold uppercase tracking-widest transition-colors duration-150"
              style={{
                fontSize: 10,
                color: isActive ? '#22d3ee' : 'rgba(255,255,255,0.32)',
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                letterSpacing: '0.12em',
              }}
            >
              {isActive && (
                <div
                  className="absolute top-0 left-2 right-2"
                  style={{
                    height: 2,
                    borderRadius: '0 0 2px 2px',
                    background: '#22d3ee',
                    boxShadow: '0 0 8px rgba(34,211,238,0.7)',
                  }}
                />
              )}
              <span>{tab.icon}</span>
              <span style={{ textShadow: isActive ? '0 0 12px rgba(34,211,238,0.6)' : 'none' }}>
                {tab.label}
              </span>
            </button>
          );
        })}
      </div>

      <div className="flex-1" />

      {/* ── External links ────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 flex-shrink-0">
        {LINKS.map(({ label, href }) => (
          <a
            key={label}
            href={href}
            target="_blank"
            rel="noreferrer"
            className="font-bold tracking-widest uppercase transition-colors duration-150 hover:text-cyan-300"
            style={{
              fontSize: 9,
              color: 'rgba(255,255,255,0.28)',
              letterSpacing: '0.1em',
              textDecoration: 'none',
            }}
          >
            [{label}]
          </a>
        ))}
      </div>
    </div>
  );
}
