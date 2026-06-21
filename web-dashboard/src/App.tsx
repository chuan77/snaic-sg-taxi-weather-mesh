import { useState } from 'react';
import { useNowcast } from './hooks/useNowcast';
import { useHotspots } from './hooks/useHotspots';
import { useTaxis } from './hooks/useTaxis';
import { useSurge } from './hooks/useSurge';
import { useClusters } from './hooks/useClusters';
import MapLayer from './components/MapLayer';
import HeaderOverlay from './components/HeaderOverlay';
import Legend from './components/Legend';
import StatusKey from './components/StatusKey';
import NowcastTimeline from './components/NowcastTimeline';
import DemandHotspots from './components/DemandHotspots';
import StatsPanel from './components/StatsPanel';
import BottomNav from './components/BottomNav';

export default function App() {
  const [activeTab, setActiveTab] = useState('map');
  const [invertHeatmap, setInvertHeatmap] = useState(false);

  const { data: nowcast } = useNowcast();
  const { data: hotspotsData } = useHotspots();
  const { data: taxisData } = useTaxis();
  const { data: surgeData } = useSurge();
  const { data: clustersData } = useClusters();

  const mapMode = activeTab === 'demand' ? 'heatmap' : 'map';

  return (
    <div className="fixed inset-0 bg-[#0a0e14] overflow-hidden">

      {/* ── Full-viewport map base ─────────────────────────────────────────── */}
      <div className="absolute inset-0">
        <MapLayer
          areas={nowcast.areas}
          taxis={taxisData.taxis}
          clusters={clustersData.clusters}
          mode={mapMode}
          invertHeatmap={invertHeatmap}
        />
      </div>

      {/* ── Top-left: header + dynamic alert ──────────────────────────────── */}
      <HeaderOverlay alert={nowcast.alert} surge={surgeData} />

      {/* ── Top-right: legend (switches content based on active tab) ──────── */}
      <Legend mode={mapMode} />

      {/* ── Right: taxi status key ────────────────────────────────────────── */}
      <StatusKey />

      {/* ── Heatmap toggle — only visible in demand tab ───────────────────── */}
      {activeTab === 'demand' && (
        <div className="absolute" style={{ top: '12px', right: '52px', zIndex: 1100 }}>
          <button
            onClick={() => setInvertHeatmap(v => !v)}
            className="px-3 py-1.5 rounded text-xs font-semibold tracking-wide transition-colors"
            style={{
              background: invertHeatmap ? 'rgba(239,68,68,0.85)' : 'rgba(34,197,94,0.85)',
              color: '#fff',
              border: 'none',
              backdropFilter: 'blur(6px)',
            }}
          >
            {invertHeatmap ? 'Supply Gap' : 'Taxi Density'}
          </button>
        </div>
      )}

      {/* ── Bottom floating panels (above nav bar) ────────────────────────── */}
      <div
        className="absolute left-3 right-3 flex gap-2.5"
        style={{ bottom: '60px', zIndex: 1001 }}
      >
        <NowcastTimeline steps={nowcast.timeline} validPeriodText={nowcast.valid_period.text} />
        <DemandHotspots
          hotspots={hotspotsData.hotspots}
          totalTaxis={hotspotsData.total_taxis_online}
          surgeZones={surgeData.zones}
        />
        <StatsPanel totalTaxis={hotspotsData.total_taxis_online} regions={nowcast.regions} />
      </div>

      {/* ── Bottom nav bar ────────────────────────────────────────────────── */}
      <BottomNav activeTab={activeTab} onTabChange={setActiveTab} />
    </div>
  );
}
