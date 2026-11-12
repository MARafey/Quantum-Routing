// DEV-ONLY fallback, used when the backend is unreachable. Never used in production builds.
const CITIES = [['Karachi', 24.86, 67.01], ['Lahore', 31.55, 74.34], ['Islamabad', 33.68, 73.05], ['Peshawar', 34.01, 71.58], ['Quetta', 30.18, 66.99],
  ['Multan', 30.2, 71.45], ['Faisalabad', 31.42, 73.08], ['Hyderabad', 25.39, 68.37], ['Sukkur', 27.7, 68.86], ['Gujranwala', 32.16, 74.19],
  ['Sialkot', 32.49, 74.53], ['Bahawalpur', 29.4, 71.68]]
const pick = (a, n) => [...a].sort(() => Math.random() - 0.5).slice(0, n).map(([name, lat, lon]) => ({ name, lat, lon }))
export function mockRandom() { const c = pick(CITIES, 10); return { hubs: c.slice(0, 2), sites: c.slice(2) } }
export function mockRun({ hubs, sites }) {
  const points = [...hubs.map((p) => ({ ...p, kind: 'hub' })), ...sites.map((p) => ({ ...p, kind: 'site' }))]
  const k = hubs.length
  const mk = () => { const o = sites.map((_, i) => k + i).sort(() => Math.random() - 0.5); return hubs.map((_, h) => [h, ...o.filter((_, i) => i % k === h)]) }
  const best = mk()
  const geometry = best.map((r) => r.map((i) => [points[i].lat, points[i].lon]))
  return { k, n: sites.length, N: 3628800, qubits: 22, matrix_source: 'mock', points,
    methods: { brute: { ms: 4200, evaluated: 3628800, coverage_pct: 100, optimal: true, makespan_s: 51600 },
      parallel: { ms: 900, evaluated: 3628800, workers: 8, coverage_pct: 100, optimal: true, makespan_s: 51600 },
      quantum: { ms: 5200, queries: 5416, queries_to_min: 5416, coverage_pct: 0.15, optimal: true, makespan_s: 51600,
        samples: Array.from({ length: 60 }, () => ({ q: 0, routes: mk() })) } },
    best: { routes: best, makespan_s: 51600, total_s: 90000, geometry, distance_km: best.map(() => 100) } }
}
