import { useNowcast } from './hooks/useNowcast';
import { useHotspots } from './hooks/useHotspots';
import { useTaxis } from './hooks/useTaxis';
import MapLayer from './components/MapLayer';
import HeaderOverlay from './components/HeaderOverlay';
import Legend from './components/Legend';
import StatusKey from './components/StatusKey';
import NowcastTimeline from './components/NowcastTimeline';
import DemandHotspots from './components/DemandHotspots';
import StatsPanel from './components/StatsPanel';
import BottomNav from './components/BottomNav';

export default function App() {
  const { data: nowcast } = useNowcast();
  const { data: hotspotsData } = useHotspots();
  const { data: taxisData } = useTaxis();

  return (
    <div className="fixed inset-0 bg-[#0a0e14] overflow-hidden">

      {/* ── Full-viewport map base ─────────────────────────────────────────── */}
      <div className="absolute inset-0">
        <MapLayer areas={nowcast.areas} taxis={taxisData.taxis} />
      </div>

      {/* ── Top-left: header + dynamic alert ──────────────────────────────── */}
      <HeaderOverlay alert={nowcast.alert} />

      {/* ── Top-right: legend ─────────────────────────────────────────────── */}
      <Legend />

      {/* ── Right: taxi status key ────────────────────────────────────────── */}
      <StatusKey />

      {/* ── Bottom floating panels (above nav bar) ────────────────────────── */}
      <div
        className="absolute left-3 right-3 flex gap-2.5"
        style={{ bottom: '60px', zIndex: 1001 }}
      >
        <NowcastTimeline steps={nowcast.timeline} validPeriodText={nowcast.valid_period.text} />
        <DemandHotspots hotspots={hotspotsData.hotspots} totalTaxis={hotspotsData.total_taxis_online} />
        <StatsPanel totalTaxis={hotspotsData.total_taxis_online} regions={nowcast.regions} />
      </div>

      {/* ── Bottom nav bar ────────────────────────────────────────────────── */}
      <BottomNav />
    </div>
  );
}
