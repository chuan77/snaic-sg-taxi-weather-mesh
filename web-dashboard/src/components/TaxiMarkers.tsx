import { Marker, Tooltip } from 'react-leaflet';
import L from 'leaflet';
import type { TaxiStatus } from '../types';
import { TAXIS, SURGE_LOCATION } from '../data/taxis';

const STATUS_CFG: Record<TaxiStatus, { bg: string; border: string; glow: string; label: string }> = {
  available: { bg: '#22c55e', border: '#4ade80', glow: 'rgba(34,197,94,0.65)',  label: 'Available' },
  hired:     { bg: '#eab308', border: '#fbbf24', glow: 'rgba(234,179,8,0.65)',  label: 'Hired'     },
  prebooked: { bg: '#3b82f6', border: '#60a5fa', glow: 'rgba(59,130,246,0.65)', label: 'Pre-booked' },
};

function taxiIcon(status: TaxiStatus) {
  const { bg, border, glow } = STATUS_CFG[status];
  return L.divIcon({
    html: `
      <svg width="22" height="15" viewBox="0 0 22 15" xmlns="http://www.w3.org/2000/svg">
        <rect x="1" y="5" width="20" height="8" rx="2.5" fill="${bg}" opacity="0.95"/>
        <path d="M4 5 L6.5 1.5 Q7.2 0.5 8.5 0.5 L13.5 0.5 Q14.8 0.5 15.5 1.5 L18 5 Z"
              fill="${bg}" opacity="0.9"/>
        <rect x="7" y="1.2" width="8" height="3.8" rx="1" fill="rgba(180,230,255,0.22)"/>
        <circle cx="5.5"  cy="13.5" r="1.8" fill="${bg}" opacity="0.85"/>
        <circle cx="16.5" cy="13.5" r="1.8" fill="${bg}" opacity="0.85"/>
        <circle cx="5.5"  cy="13.5" r="0.7" fill="rgba(0,0,0,0.45)"/>
        <circle cx="16.5" cy="13.5" r="0.7" fill="rgba(0,0,0,0.45)"/>
      </svg>
    `,
    className: '',
    iconSize: [22, 15],
    iconAnchor: [11, 15],
  });
}

const surgeIcon = L.divIcon({
  html: '<div class="surge-marker">+$6 Surge</div>',
  className: '',
  iconSize: [90, 32],
  iconAnchor: [45, 16],
});

export default function TaxiMarkers() {
  return (
    <>
      {TAXIS.map((taxi) => (
        <Marker key={taxi.id} position={[taxi.lat, taxi.lng]} icon={taxiIcon(taxi.status)}>
          <Tooltip direction="top" offset={[0, -12]} opacity={0.97}>
            <div style={{ fontFamily: "'Barlow Semi Condensed', sans-serif", minWidth: 120 }}>
              <div style={{ fontWeight: 800, fontSize: 13, letterSpacing: 1, marginBottom: 4 }}>
                🚕 {taxi.id}
              </div>
              <div style={{ color: STATUS_CFG[taxi.status].bg, fontWeight: 700, fontSize: 11 }}>
                ● {STATUS_CFG[taxi.status].label}
              </div>
              <div style={{ color: 'rgba(255,255,255,0.55)', fontSize: 11, marginTop: 2 }}>
                📍 {taxi.zone}
              </div>
            </div>
          </Tooltip>
        </Marker>
      ))}

      {/* Orchard surge marker */}
      <Marker position={[SURGE_LOCATION.lat, SURGE_LOCATION.lng]} icon={surgeIcon}>
        <Tooltip direction="top" offset={[0, -20]} opacity={0.97}>
          <div style={{ fontFamily: "'Barlow Semi Condensed', sans-serif" }}>
            <div style={{ fontWeight: 800, fontSize: 13 }}>⚡ Surge Pricing</div>
            <div style={{ color: '#f472b6', fontWeight: 700, fontSize: 11, marginTop: 2 }}>
              Orchard Road — $6 surcharge
            </div>
          </div>
        </Tooltip>
      </Marker>
    </>
  );
}
