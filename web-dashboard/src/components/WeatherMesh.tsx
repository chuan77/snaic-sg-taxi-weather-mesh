import { Marker } from 'react-leaflet';
import L from 'leaflet';
import { AREA_LABELS } from '../data/weather';

function areaLabelIcon(label: string, main = false) {
  return L.divIcon({
    html:       `<div class="map-label${main ? ' map-label-main' : ''}">${label}</div>`,
    className:  '',
    iconSize:   main ? [200, 28] : [120, 18],
    iconAnchor: main ? [100, 14] : [60, 9],
  });
}

/** Geographic area labels only — precipitation intensity is rendered by PrecipitationOverlay. */
export default function WeatherMesh() {
  return (
    <>
      {AREA_LABELS.map(({ pos, label, main }) => (
        <Marker
          key={label}
          position={pos}
          icon={areaLabelIcon(label, main)}
          interactive={false}
        />
      ))}
    </>
  );
}
