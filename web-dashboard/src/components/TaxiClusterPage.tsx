import { useMemo, useCallback } from 'react';
import { MapContainer, TileLayer, GeoJSON, Marker } from 'react-leaflet';
import L, { type Layer } from 'leaflet';
import { useTaxis } from '../hooks/useTaxis';
import { useSubzoneCounts } from '../hooks/useSubzoneCounts';
import type { SubzoneFeature, SubzoneCollection } from '../types';

const SG_CENTER: [number, number] = [1.3521, 103.8198];
const SG_BOUNDS: [[number, number], [number, number]] = [[1.1, 103.5], [1.5, 104.1]];
const COLOR_STOPS = ['#f7f7f7', '#fee0d2', '#fcbba1', '#fc9272', '#de2d26', '#a50f15'];

function countToColor(count: number, max: number): string {
  if (max === 0 || count === 0) return COLOR_STOPS[0];
  const t = Math.min(count / max, 1);
  const idx = Math.min(Math.floor(t * (COLOR_STOPS.length - 1)), COLOR_STOPS.length - 2);
  return COLOR_STOPS[idx + 1];
}

// Average of exterior ring coords → centroid [lat, lng]
function polygonCentroid(coords: number[][]): [number, number] {
  let sumLng = 0, sumLat = 0;
  for (const [lng, lat] of coords) { sumLng += lng; sumLat += lat; }
  return [sumLat / coords.length, sumLng / coords.length];
}

function featureCentroid(feature: SubzoneFeature): [number, number] {
  const geom = feature.geometry;
  const ring = geom.type === 'Polygon'
    ? (geom.coordinates as number[][][])[0]
    : (geom.coordinates as number[][][][])[0][0];
  return polygonCentroid(ring);
}

export default function TaxiClusterPage() {
  const { data: taxiData, loading: taxiLoading } = useTaxis();
  const { counts, maxCount, geoJson, loading: geoLoading } = useSubzoneCounts(taxiData.taxis);

  // Style each subzone polygon
  const styleFeature = useMemo(() => (feature?: SubzoneFeature) => {
    const count = counts.get(feature?.properties.SUBZONE_N ?? '') ?? 0;
    return {
      fillColor: countToColor(count, maxCount),
      fillOpacity: count > 0 ? 0.65 : 0.15,
      color: '#555',
      weight: 0.8,
    };
  }, [counts, maxCount]);

  // Tooltip on hover
  const onEachFeature = useCallback((feature: SubzoneFeature, layer: Layer) => {
    const count = counts.get(feature.properties.SUBZONE_N) ?? 0;
    layer.bindTooltip(
      `<strong>${feature.properties.SUBZONE_N}</strong><br/>` +
      `${feature.properties.PLN_AREA_N}<br/>` +
      `<span style="font-size:1.1em;font-weight:600">${count} taxi${count !== 1 ? 's' : ''}</span>`,
      { sticky: true, className: 'subzone-tooltip' }
    );
  }, [counts]);

  // Count badge markers — only for subzones that have taxis
  const countMarkers = useMemo(() => {
    if (!geoJson || maxCount === 0) return [];
    return (geoJson as SubzoneCollection).features
      .filter(f => (counts.get(f.properties.SUBZONE_N) ?? 0) > 0)
      .map(f => {
        const count = counts.get(f.properties.SUBZONE_N)!;
        const [lat, lng] = featureCentroid(f);
        const icon = L.divIcon({
          className: '',
          html: `<div style="
            background:${countToColor(count, maxCount)};
            color:${count / maxCount > 0.5 ? '#fff' : '#222'};
            border-radius:4px;padding:1px 5px;font-size:11px;
            font-weight:700;white-space:nowrap;
            border:1px solid rgba(0,0,0,0.25);
            box-shadow:0 1px 3px rgba(0,0,0,0.4)">${count}</div>`,
          iconAnchor: [0, 0],
        });
        return { lat, lng, count, name: f.properties.SUBZONE_N, icon };
      });
  }, [geoJson, counts, maxCount]);

  const isLoading = taxiLoading || geoLoading;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#0f1117' }}>
      <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
        <MapContainer
          center={SG_CENTER}
          zoom={11}
          maxBounds={SG_BOUNDS}
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://carto.com/">CARTO</a>'
          />
          {geoJson && (
            <GeoJSON
              key={`${maxCount}-${taxiData.total}`}
              data={geoJson as GeoJSON.FeatureCollection}
              style={styleFeature as (f?: GeoJSON.Feature) => object}
              onEachFeature={onEachFeature as (f: GeoJSON.Feature, l: Layer) => void}
            />
          )}
          {countMarkers.map(m => (
            <Marker key={m.name} position={[m.lat, m.lng]} icon={m.icon} />
          ))}
        </MapContainer>

        {isLoading && (
          <div style={{
            position: 'absolute', top: 60, left: 0, right: 0, textAlign: 'center',
            color: '#aaa', fontSize: 13, pointerEvents: 'none',
          }}>
            Computing subzone counts…
          </div>
        )}

        {/* Legend */}
        <div style={{
          position: 'absolute', bottom: 24, right: 12, zIndex: 1000,
          background: 'rgba(15,17,23,0.9)', borderRadius: 8,
          padding: '8px 12px', color: '#eee', fontSize: 11, border: '1px solid #333',
        }}>
          <div style={{ marginBottom: 4, fontWeight: 600 }}>Taxis / Subzone</div>
          {COLOR_STOPS.slice(1).map((c, i) => (
            <div key={c} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
              <span style={{ width: 12, height: 12, background: c, display: 'inline-block', borderRadius: 2 }} />
              <span>
                {i === 0 ? '1–' : `${Math.round((i / (COLOR_STOPS.length - 1)) * maxCount)}+`}
              </span>
            </div>
          ))}
          <div style={{ marginTop: 6, color: '#888', borderTop: '1px solid #333', paddingTop: 4 }}>
            {taxiData.total} taxis total
          </div>
        </div>
      </div>

      {/* Top-20 table */}
      <div style={{
        height: 160, overflowY: 'auto', background: '#1a1d27',
        borderTop: '1px solid #2a2d3a', padding: '8px 12px',
        flexShrink: 0,
      }}>
        <div style={{ fontSize: 11, color: '#888', marginBottom: 4, fontWeight: 600 }}>
          TOP SUBZONES BY TAXI COUNT
        </div>
        {[...counts.entries()]
          .sort((a, b) => b[1] - a[1])
          .slice(0, 20)
          .map(([name, count], i) => (
            <div key={name} style={{
              display: 'flex', justifyContent: 'space-between',
              fontSize: 11, color: '#ccc', padding: '2px 0',
              borderBottom: '1px solid #22263a',
            }}>
              <span style={{ color: '#888', marginRight: 6 }}>{i + 1}.</span>
              <span style={{ flex: 1 }}>{name}</span>
              <span style={{
                fontWeight: 700, color: countToColor(count, maxCount),
                minWidth: 24, textAlign: 'right',
              }}>{count}</span>
            </div>
          ))
        }
        {counts.size === 0 && (
          <div style={{ color: '#555', fontSize: 11 }}>Loading…</div>
        )}
      </div>
    </div>
  );
}
