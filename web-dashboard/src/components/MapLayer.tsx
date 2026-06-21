import { MapContainer, TileLayer } from 'react-leaflet';
import WeatherMesh from './WeatherMesh';
import TaxiDotLayer from './TaxiDotLayer';
import DemandHeatLayer from './DemandHeatLayer';
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
  mode?: 'map' | 'heatmap';
}

export default function MapLayer({ areas = [], taxis = [], mode = 'map' }: Props) {
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

      {/* Map view: weather overlay + taxi dots */}
      {mode === 'map' && <PrecipitationOverlay areas={areas} />}
      {mode === 'map' && <TaxiDotLayer taxis={taxis} />}

      {/* Heatmap view: demand density */}
      {mode === 'heatmap' && <DemandHeatLayer taxis={taxis} />}

      {/* Area labels visible in both modes */}
      <WeatherMesh />
    </MapContainer>
  );
}
