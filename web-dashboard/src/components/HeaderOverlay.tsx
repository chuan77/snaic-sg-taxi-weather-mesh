import { useState, useEffect } from 'react';
import type { NowcastAlert } from '../types';

interface Props {
  alert: NowcastAlert;
}

export default function HeaderOverlay({ alert }: Props) {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const dateStr = now.toLocaleDateString('en-SG', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });
  const timeStr = now.toLocaleTimeString('en-SG', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  });

  // Active alerts use amber; informational notices use a muted blue-grey
  const bannerStyle = alert.active
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

  const iconColor    = alert.active ? '#fbbf24' : '#7dd3fc';
  const messageColor = alert.active ? '#fcd34d' : '#bae6fd';
  const icon         = alert.active ? '⚠'       : 'ℹ';

  return (
    <div
      className="absolute top-3 left-3"
      style={{ zIndex: 1001, maxWidth: 430, pointerEvents: 'none' }}
    >
      <div className="glass p-4" style={{ pointerEvents: 'auto' }}>
        {/* Title */}
        <div className="flex items-center gap-2.5 mb-1">
          <span className="text-2xl leading-none">🇸🇬</span>
          <h1
            className="text-white font-black tracking-[0.14em] uppercase leading-none"
            style={{ fontSize: 17 }}
          >
            SG Taxi Weather Mesh
          </h1>
        </div>

        {/* Live clock */}
        <p
          className="font-semibold uppercase tracking-widest mb-3"
          style={{ fontSize: 10, color: '#22d3ee' }}
        >
          Live: {dateStr} | {timeStr}
        </p>

        {/* Dynamic weather alert */}
        <div
          className="flex items-start gap-2 px-3 py-2 rounded-2xl"
          style={bannerStyle}
        >
          <span className="mt-0.5" style={{ fontSize: 14, color: iconColor }}>{icon}</span>
          <p className="font-semibold leading-snug" style={{ fontSize: 11, color: messageColor }}>
            {alert.message}
          </p>
        </div>
      </div>
    </div>
  );
}
