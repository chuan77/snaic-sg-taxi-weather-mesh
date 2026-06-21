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
  const [showHeatmap, setShowHeatmap] = useState(true);

  const { data: nowcast } = useNowcast();
  const { data: hotspotsData } = useHotspots();
  const { data: taxisData } = useTaxis();
  const { data: surgeData } = useSurge();
  const { data: clustersData } = useClusters();

  const mapMode = activeTab === 'demand' ? 'heatmap' : 'map';

  function handleTabChange(id: string) {
    if (id === 'demand') setShowHeatmap(true);
    setActiveTab(id);
  }

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
          showHeatmap={showHeatmap}
        />
      </div>

      {/* ── Top-left: header + dynamic alert ──────────────────────────────── */}
      <HeaderOverlay alert={nowcast.alert} surge={surgeData} />

      {/* ── Top-right: legend (switches content based on active tab) ──────── */}
      <Legend mode={mapMode} invert={invertHeatmap} />

      {/* ── Right: taxi status key ────────────────────────────────────────── */}
      <StatusKey />

      {/* ── Heatmap controls — only visible in demand tab ─────────────────── */}
      {activeTab === 'demand' && (
        <div
          className="absolute flex gap-2"
          style={{ top: '12px', right: '52px', zIndex: 1100 }}
        >
          {/* Visibility toggle */}
          <button
            onClick={() => setShowHeatmap(v => !v)}
            className="px-3 py-1.5 rounded text-xs font-semibold tracking-wide transition-colors"
            style={{
              background: showHeatmap
                ? 'rgba(34,211,238,0.20)'
                : 'rgba(100,116,139,0.40)',
              color: showHeatmap ? '#67e8f9' : 'rgba(255,255,255,0.55)',
              border: `1px solid ${showHeatmap ? 'rgba(34,211,238,0.40)' : 'rgba(100,116,139,0.40)'}`,
              backdropFilter: 'blur(6px)',
            }}
          >
            {showHeatmap ? 'Hide Heatmap' : 'Show Heatmap'}
          </button>

          {/* Invert toggle — dimmed when layer is hidden */}
          <button
            onClick={() => setInvertHeatmap(v => !v)}
            className={`px-3 py-1.5 rounded text-xs font-semibold tracking-wide transition-colors ${!showHeatmap ? 'opacity-40 pointer-events-none' : ''}`}
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
      <BottomNav activeTab={activeTab} onTabChange={handleTabChange} />
    </div>
  );
}
