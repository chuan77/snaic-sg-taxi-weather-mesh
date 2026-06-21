import { Circle, Tooltip } from 'react-leaflet';
import type { ClusterEntry } from '../types';

interface Props {
  clusters: ClusterEntry[];
}

// Color based on taxi count (size of cluster)
function clusterColor(count: number): string {
  if (count >= 200) return '#ef4444'; // red  — large
  if (count >= 100) return '#f97316'; // orange — medium
  if (count >= 50)  return '#eab308'; // yellow — small-medium
  return '#3b82f6';                   // blue  — small
}

export default function ClusterOverlay({ clusters }: Props) {
  if (clusters.length === 0) return null;

  return (
    <>
      {clusters.map((c) => {
        const color = clusterColor(c.count);
        return (
          <Circle
            key={c.id}
            center={[c.centroid_lat, c.centroid_lng]}
            radius={c.radius_km * 1000}
            pathOptions={{
              color,
              fillColor: color,
              fillOpacity: 0.12,
              opacity: 0.55,
              weight: 1.5,
            }}
          >
            <Tooltip direction="top" sticky>
              <div style={{ fontFamily: "'Barlow Semi Condensed', sans-serif", minWidth: 120 }}>
                <div style={{ fontWeight: 800, fontSize: 12, marginBottom: 3 }}>{c.name}</div>
                <div style={{ color, fontWeight: 700, fontSize: 11 }}>{c.count} taxis</div>
                <div style={{ color: 'rgba(255,255,255,0.5)', fontSize: 10, marginTop: 2 }}>
                  r ≈ {c.radius_km} km
                </div>
              </div>
            </Tooltip>
          </Circle>
        );
      })}
    </>
  );
}
