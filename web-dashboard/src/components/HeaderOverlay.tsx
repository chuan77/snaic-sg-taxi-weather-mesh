import { useState, useEffect } from 'react';
import type { NowcastAlert, SurgeData } from '../types';

interface Props {
  alert: NowcastAlert;
  surge?: SurgeData;
}

export default function HeaderOverlay({ alert, surge }: Props) {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const dateStr = now.toLocaleDateString('en-SG', {
    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
  });
  const timeStr = now.toLocaleTimeString('en-SG', {
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true,
  });

  // Surge predictor takes priority over nowcast alert when active and has a message
  const surgeActive  = Boolean(surge?.alert_active && surge?.alert_message);
  const isActive     = surgeActive || alert.active;
  const message      = surgeActive ? surge!.alert_message : alert.message;

  const bannerStyle = isActive
    ? {
        background: 'rgba(245, 158, 11, 0.10)',
        border:     '1px solid rgba(245, 158, 11, 0.38)',
        boxShadow:  '0 0 14px rgba(245, 158, 11, 0.16)',
      }
    : {
        background: 'rgba(14, 165, 233, 0.07)',
        border:     '1px solid rgba(14, 165, 233, 0.20)',
        boxShadow:  'none',
      };

  const iconColor    = isActive ? '#fbbf24' : '#7dd3fc';
  const messageColor = isActive ? '#fcd34d' : '#bae6fd';
  const icon         = isActive ? '⚠'       : 'ℹ';

  return (
    <div
      className="absolute top-3 left-3"
      style={{ zIndex: 1001, maxWidth: 430, pointerEvents: 'none' }}
    >
      <div className="glass p-4" style={{ pointerEvents: 'auto' }}>
        <div className="flex items-center gap-2.5 mb-1">
          <span className="text-2xl leading-none">🇸🇬</span>
          <h1
            className="text-white font-black tracking-[0.14em] uppercase leading-none"
            style={{ fontSize: 17 }}
          >
            SG Taxi Weather Mesh
          </h1>
        </div>

        <p
          className="font-semibold uppercase tracking-widest mb-3"
          style={{ fontSize: 10, color: '#22d3ee' }}
        >
          Live: {dateStr} | {timeStr}
        </p>

        <div
          className="flex items-start gap-2 px-3 py-2 rounded-2xl"
          style={bannerStyle}
        >
          <span className="mt-0.5" style={{ fontSize: 14, color: iconColor }}>{icon}</span>
          <div>
            <p className="font-semibold leading-snug" style={{ fontSize: 11, color: messageColor }}>
              {message}
            </p>
            {surgeActive && (
              <p style={{ fontSize: 9, color: 'rgba(252,211,77,0.55)', marginTop: 2 }}>
                AI demand forecast · LMStudio
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
