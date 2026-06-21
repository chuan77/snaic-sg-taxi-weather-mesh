import type { Taxi } from '../types';

// 30 taxis: 10 available (west/north), 15 hired (central/east), 5 pre-booked
export const TAXIS: Taxi[] = [
  // Available — green, mostly in clear western zones
  { id: 'T001', lat: 1.350, lng: 103.695, status: 'available', zone: 'Jurong West' },
  { id: 'T002', lat: 1.382, lng: 103.718, status: 'available', zone: 'Bukit Panjang' },
  { id: 'T003', lat: 1.334, lng: 103.706, status: 'available', zone: 'Clementi' },
  { id: 'T004', lat: 1.291, lng: 103.745, status: 'available', zone: 'Queenstown' },
  { id: 'T005', lat: 1.422, lng: 103.727, status: 'available', zone: 'Woodlands' },
  { id: 'T006', lat: 1.362, lng: 103.661, status: 'available', zone: 'Jurong Island' },
  { id: 'T007', lat: 1.404, lng: 103.797, status: 'available', zone: 'Yishun' },
  { id: 'T008', lat: 1.314, lng: 103.762, status: 'available', zone: 'Buona Vista' },
  { id: 'T009', lat: 1.446, lng: 103.678, status: 'available', zone: 'Lim Chu Kang' },
  { id: 'T010', lat: 1.278, lng: 103.694, status: 'available', zone: 'Pasir Panjang' },

  // Hired — yellow, clustered in storm/heavy-rain central + east (high demand)
  { id: 'T011', lat: 1.303, lng: 103.832, status: 'hired', zone: 'Orchard' },
  { id: 'T012', lat: 1.285, lng: 103.854, status: 'hired', zone: 'Marina Bay' },
  { id: 'T013', lat: 1.320, lng: 103.843, status: 'hired', zone: 'Novena' },
  { id: 'T014', lat: 1.282, lng: 103.862, status: 'hired', zone: 'CBD' },
  { id: 'T015', lat: 1.350, lng: 103.871, status: 'hired', zone: 'Bishan' },
  { id: 'T016', lat: 1.366, lng: 103.906, status: 'hired', zone: 'Serangoon' },
  { id: 'T017', lat: 1.334, lng: 103.925, status: 'hired', zone: 'Tampines' },
  { id: 'T018', lat: 1.357, lng: 103.987, status: 'hired', zone: 'Pasir Ris' },
  { id: 'T019', lat: 1.362, lng: 103.991, status: 'hired', zone: 'Changi Airport' },
  { id: 'T020', lat: 1.271, lng: 103.819, status: 'hired', zone: 'HarbourFront' },
  { id: 'T021', lat: 1.309, lng: 103.896, status: 'hired', zone: 'Paya Lebar' },
  { id: 'T022', lat: 1.327, lng: 103.961, status: 'hired', zone: 'Bedok' },
  { id: 'T023', lat: 1.280, lng: 103.876, status: 'hired', zone: 'Tanjong Pagar' },
  { id: 'T024', lat: 1.295, lng: 103.853, status: 'hired', zone: 'Marina Bay Sands' },
  { id: 'T025', lat: 1.374, lng: 103.949, status: 'hired', zone: 'Tampines North' },

  // Pre-booked — blue, scattered
  { id: 'T026', lat: 1.383, lng: 103.848, status: 'prebooked', zone: 'Ang Mo Kio' },
  { id: 'T027', lat: 1.443, lng: 103.797, status: 'prebooked', zone: 'Woodlands Central' },
  { id: 'T028', lat: 1.329, lng: 103.803, status: 'prebooked', zone: 'Toa Payoh' },
  { id: 'T029', lat: 1.257, lng: 103.822, status: 'prebooked', zone: 'Sentosa' },
  { id: 'T030', lat: 1.406, lng: 103.902, status: 'prebooked', zone: 'Sengkang' },
];

// Orchard surge pricing location
export const SURGE_LOCATION = { lat: 1.3048, lng: 103.8318 };
