// DEV-ONLY fallback, used when the backend is unreachable. Never used in production builds.
const CITIES = [['Karachi', 24.86, 67.01], ['Lahore', 31.55, 74.34], ['Islamabad', 33.68, 73.05], ['Peshawar', 34.01, 71.58], ['Quetta', 30.18, 66.99],
  ['Multan', 30.2, 71.45], ['Faisalabad', 31.42, 73.08], ['Hyderabad', 25.39, 68.37], ['Sukkur', 27.7, 68.86], ['Gujranwala', 32.16, 74.19],
  ['Sialkot', 32.49, 74.53], ['Bahawalpur', 29.4, 71.68]]
const pick = (a, n) => [...a].sort(() => Math.random() - 0.5).slice(0, n).map(([name, lat, lon]) => ({ name, lat, lon }))
const REGION_CITIES = {
  'turkiye-syria': [['Gaziantep', 37.07, 37.38], ['Hatay', 36.2, 36.16], ['Kahramanmaras', 37.58, 36.94], ['Malatya', 38.35, 38.31], ['Adiyaman', 37.76, 38.28], ['Aleppo', 36.2, 37.16], ['Idlib', 35.93, 36.63], ['Adana', 37.0, 35.32], ['Osmaniye', 37.07, 36.25], ['Latakia', 35.52, 35.79], ['Sanliurfa', 37.16, 38.79], ['Diyarbakir', 37.91, 40.23]],
  'bengal-floods': [['Dhaka', 23.81, 90.41], ['Sylhet', 24.9, 91.87], ['Rangpur', 25.74, 89.25], ['Khulna', 22.85, 89.54], ['Barisal', 22.7, 90.37], ['Kolkata', 22.57, 88.36], ['Jalpaiguri', 26.54, 88.72], ['Cumilla', 23.46, 91.18], ['Mymensingh', 24.75, 90.4], ['Malda', 25.01, 88.14], ['Bogura', 24.85, 89.37], ['Silchar', 24.83, 92.78]],
  'nepal-himalaya': [['Kathmandu', 27.72, 85.32], ['Pokhara', 28.21, 83.99], ['Gorkha', 28.0, 84.63], ['Dhading', 27.87, 84.9], ['Biratnagar', 26.45, 87.27], ['Nepalgunj', 28.05, 81.62], ['Janakpur', 26.73, 85.93], ['Bharatpur', 27.68, 84.43], ['Dharan', 26.81, 87.28], ['Jomsom', 28.78, 83.72], ['Butwal', 27.7, 83.45], ['Dhangadhi', 28.7, 80.59]],
}
export const MOCK_REGIONS = [
  { id: 'turkiye-syria', name: 'Turkiye / Syria earthquake', bbox: [[35.5, 35.5], [38.6, 40.5]] },
  { id: 'bengal-floods', name: 'Bengal floods', bbox: [[22.0, 87.8], [26.8, 92.8]] },
  { id: 'nepal-himalaya', name: 'Nepal Himalaya', bbox: [[26.3, 80.5], [28.9, 88.2]] },
]
export function mockRegions() { return MOCK_REGIONS }
export function mockRandom(path = '') {
  const id = new URLSearchParams(path.split('?')[1] || '').get('region')
  const c = pick(REGION_CITIES[id] || CITIES, 11); return { hubs: c.slice(0, 3), sites: c.slice(3) }
}
export async function mockRun({ hubs, sites, region }) {
  await new Promise((r) => setTimeout(r, 3500))
  const points = [...hubs.map((p) => ({ ...p, kind: 'hub' })), ...sites.map((p) => ({ ...p, kind: 'site' }))]
  const k = hubs.length
  const mk = () => { const o = sites.map((_, i) => k + i).sort(() => Math.random() - 0.5); return hubs.map((_, h) => [h, ...o.filter((_, i) => i % k === h)]) }
  const best = mk()
  const geometry = best.map((r) => r.map((i) => [points[i].lat, points[i].lon]))
  return { region, k, n: sites.length, N: 3628800, qubits: 22, matrix_source: 'mock', points,
    methods: { brute: { ms: 4200, evaluated: 3628800, coverage_pct: 100, optimal: true, makespan_s: 51600 },
      parallel: { ms: 900, evaluated: 3628800, workers: 8, coverage_pct: 100, optimal: true, makespan_s: 51600 },
      quantum: { ms: 5200, queries: 5416, queries_to_min: 5416, coverage_pct: 0.15, optimal: true, makespan_s: 51600,
        samples: [] },
      quantum_ws: { ms: 3100, queries: 1900, queries_to_min: 1900, heuristic_ms: 40, heuristic_evals: 6200, heuristic_makespan_s: 53000, coverage_pct: 0.06, total_coverage_pct: 0.2, optimal: true, makespan_s: 51600, samples: [] } },
    best: { routes: best, makespan_s: 51600, total_s: 90000, geometry, distance_km: best.map(() => 100) } }
}
