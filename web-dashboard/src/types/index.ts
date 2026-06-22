export type TaxiStatus = 'available' | 'hired' | 'prebooked';

export interface Taxi {
  id: string;
  lat: number;
  lng: number;
  status: TaxiStatus;
  zone: string;
}

export type WeatherIntensity = 'clear' | 'drizzle' | 'moderate' | 'heavy' | 'storm';

export interface WeatherCell {
  id: string;
  /** [[sw_lat, sw_lng], [ne_lat, ne_lng]] */
  bounds: [[number, number], [number, number]];
  intensity: WeatherIntensity;
}

export interface Hotspot {
  id: string;
  name: string;
  level: 'high' | 'medium' | 'low';
  lat: number;
  lng: number;
}

export interface HotspotEntry {
  id: string;
  name: string;
  level: 'high' | 'medium' | 'low';
  taxi_count: number;
  delta_count?: number | null;
  sdi: number;
  sdi_label: string;
  lat: number;
  lng: number;
}

export interface SurgeZone {
  id: string;
  name: string;
  lat: number;
  lng: number;
  nearest_area: string;
  forecast: string;
  intensity: string;
  surge_score: number;
  alert_level: 'critical' | 'high' | 'moderate' | 'low';
  valid_period_start: string;
}

export interface SurgeData {
  updated_at: string;
  alert_active: boolean;
  alert_message: string;
  zones: SurgeZone[];
}

export interface ClusterEntry {
  id: string;
  name: string;
  centroid_lat: number;
  centroid_lng: number;
  count: number;
  radius_km: number;
}

export interface ClustersData {
  updated_at: string;
  snapshot_timestamp: string;
  cluster_count: number;
  silhouette_score: number | null;
  clusters: ClusterEntry[];
}

export interface HotspotsData {
  updated_at: string;
  total_taxis_online: number;
  snapshot_timestamp: string;
  fleet_coverage_score?: number | null;
  hotspots: HotspotEntry[];
}

export interface TaxiPoint {
  lat: number;
  lng: number;
}

export interface TaxisData {
  updated_at: string;
  snapshot_timestamp: string;
  total: number;
  taxis: TaxiPoint[];
}

export interface NowcastStep {
  time: string;
  label: string;
  intensity: WeatherIntensity;
}

export interface NowcastArea {
  name: string;
  region: string;
  forecast: string;
  intensity: WeatherIntensity;
  latitude: number;
  longitude: number;
}

export interface NowcastAlert {
  active: boolean;
  message: string;
}

export interface NowcastData {
  updated_at: string;
  valid_period: { start: string; end: string; text: string };
  alert: NowcastAlert;
  /** Dominant intensity per planning region: North/South/East/West/Central */
  regions: Record<string, WeatherIntensity>;
  areas: NowcastArea[];
  timeline: NowcastStep[];
}

export interface Forecast24hPeriod {
  time_text: string;
  start: string;
  end: string;
  dominant_intensity: WeatherIntensity;
  dominant_forecast: string;
  regions: Record<string, WeatherIntensity>;
}

export interface Forecast24hData {
  updated_at: string;
  valid_period: { start: string; end: string };
  general: {
    forecast: string;
    intensity: WeatherIntensity;
    temp_low: number;
    temp_high: number;
    rh_low: number;
    rh_high: number;
  };
  periods: Forecast24hPeriod[];
}

export interface ForecastZone {
  id: string;
  name: string;
  current_count: number;
  predicted_count: number;
  delta: number;
}

export interface DemandForecastData {
  generated_at: string;
  horizon_minutes: number;
  sufficient_data: boolean;
  model_mae: number | null;
  zones: ForecastZone[];
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface PlanningAreaEntry {
  name: string;
  region: string;
  count: number;
}

export interface SubzonesData {
  generated_at: string;
  total_assigned: number;
  unassigned: number;
  planning_areas: PlanningAreaEntry[];
}
