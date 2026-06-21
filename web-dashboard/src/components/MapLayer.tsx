import { MapContainer, TileLayer } from 'react-leaflet';
import WeatherMesh from './WeatherMesh';
import TaxiDotLayer from './TaxiDotLayer';
import { PrecipitationOverlay } from './PrecipitationOverlay';
import type { NowcastArea, TaxiPoint } from '../types';

const DARK_TILES =
  'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';
const ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> ' +
  '&copy; <a href="https://carto.com/attributions">CARTO</a>';

interface Props {
  areas?: NowcastArea[];
  taxis?: TaxiPoint[];
}

export default function MapLayer({ areas = [], taxis = [] }: Props) {
  return (
    <MapContainer
      center={[1.352, 103.819]}
      zoom={12}
      minZoom={10}
      maxZoom={16}
      className="w-full h-full"
      zoomControl={false}
      scrollWheelZoom
    >
      <TileLayer url={DARK_TILES} attribution={ATTRIBUTION} subdomains="abcd" maxZoom={20} />

      {/* Gradient precipitation blobs — below taxi dots */}
      <PrecipitationOverlay areas={areas} />

      {/* Geographic area labels */}
      <WeatherMesh />

      {/* Live taxi positions — canvas dot layer, z-index 450 */}
      <TaxiDotLayer taxis={taxis} />
    </MapContainer>
  );
}
