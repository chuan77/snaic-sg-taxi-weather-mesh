import { useState } from 'react';
import { useNowcast } from './hooks/useNowcast';
import { useHotspots } from './hooks/useHotspots';
import { useTaxis } from './hooks/useTaxis';
import { useSurge } from './hooks/useSurge';
import { useClusters } from './hooks/useClusters';
import { useForecast24h } from './hooks/useForecast24h';
import { useForecast } from './hooks/useForecast';
import { useSubzones } from './hooks/useSubzones';
import MapLayer from './components/MapLayer';
import HeaderOverlay from './components/HeaderOverlay';
import Legend from './components/Legend';
import StatusKey from './components/StatusKey';
import NowcastTimeline from './components/NowcastTimeline';
import Forecast24hTimeline from './components/Forecast24hTimeline';
import DemandHotspots from './components/DemandHotspots';
import StatsPanel from './components/StatsPanel';
import AlertsPanel from './components/AlertsPanel';
import BottomNav from './components/BottomNav';
import ChatPanel from './components/ChatPanel';
import TaxiClusterPage from './components/TaxiClusterPage';

export default function App() {
  const [activeTab, setActiveTab] = useState('map');
  const [invertHeatmap, setInvertHeatmap] = useState(false);

  const { data: nowcast } = useNowcast();
  const { data: hotspotsData } = useHotspots();
  const { data: taxisData } = useTaxis();
  const { data: surgeData } = useSurge();
  const { data: clustersData } = useClusters();
  const { data: forecast24h } = useForecast24h();
  const { data: forecastData } = useForecast();
  const { data: subzonesData } = useSubzones();

  const mapMode = activeTab === 'demand' ? 'heatmap' : 'map';

  return (
    <div className="fixed inset-0 bg-[#0a0e14] overflow-hidden">

      {activeTab === 'cluster' ? (
        <div className="absolute inset-0" style={{ bottom: '56px' }}>
          <TaxiClusterPage />
        </div>
      ) : (
        <>
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
          <Legend mode={mapMode} invert={invertHeatmap} />

          {/* ── Right: taxi status key ────────────────────────────────────────── */}
          <StatusKey />

          {/* ── Invert toggle — only visible in demand tab ────────────────────── */}
          {activeTab === 'demand' && (
            <div
              className="absolute"
              style={{ top: '12px', right: '52px', zIndex: 1100 }}
            >
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

          {/* ── Bottom floating panels / Alerts page ─────────────────────────── */}
          {activeTab === 'alerts' ? (
            <AlertsPanel surge={surgeData} nowcastAlert={nowcast.alert} />
          ) : (
            <div
              className="absolute left-3 right-3 flex gap-2.5"
              style={{ bottom: '60px', zIndex: 1001 }}
            >
              <NowcastTimeline steps={nowcast.timeline} validPeriodText={nowcast.valid_period.text} />
              <Forecast24hTimeline data={forecast24h} />
              <DemandHotspots
                hotspots={hotspotsData.hotspots}
                totalTaxis={hotspotsData.total_taxis_online}
                surgeZones={surgeData.zones}
                forecastZones={forecastData.zones}
                planningAreas={subzonesData.planning_areas}
              />
              <StatsPanel
                totalTaxis={hotspotsData.total_taxis_online}
                regions={nowcast.regions}
                coverageScore={hotspotsData.fleet_coverage_score ?? null}
              />
            </div>
          )}
        </>
      )}

      {/* ── Chat assistant — always rendered, manages own open state ─────── */}
      <ChatPanel />

      {/* ── Bottom nav bar ────────────────────────────────────────────────── */}
      <BottomNav activeTab={activeTab} onTabChange={setActiveTab} />
    </div>
  );
}
