export const METHODS = {
  brute: { key: 'brute', name: 'Brute force', color: '#7c5e3c' },
  parallel: { key: 'parallel', name: 'Parallel (8 workers)', color: '#0b7a69' },
  quantum: { key: 'quantum', name: 'Quantum search (simulated)', color: '#3451c6' },
  quantum_ws: { key: 'quantum_ws', name: 'Quantum + warm start (simulated)', color: '#7048b8' },
}

export const PAKISTAN = { id: 'pakistan', name: 'Pakistan', bbox: [[23.6, 60.9], [37.1, 77.8]] }

/* accept [[latMin,lonMin],[latMax,lonMax]], {lat_min,...}, {south,west,north,east}, or flat [latMin,lonMin,latMax,lonMax] */
export function normBbox(b) {
  if (!b) return null
  if (Array.isArray(b)) {
    if (b.length === 4 && b.every((x) => typeof x === 'number')) return [[b[0], b[1]], [b[2], b[3]]]
    if (b.length === 2 && Array.isArray(b[0]) && Array.isArray(b[1])) return [[+b[0][0], +b[0][1]], [+b[1][0], +b[1][1]]]
    return null
  }
  const g = (...ks) => { for (const k of ks) if (b[k] != null) return +b[k]; return NaN }
  const r = [[g('lat_min', 'latMin', 'south', 'min_lat'), g('lon_min', 'lonMin', 'west', 'min_lon')], [g('lat_max', 'latMax', 'north', 'max_lat'), g('lon_max', 'lonMax', 'east', 'max_lon')]]
  return r.flat().every(Number.isFinite) ? r : null
}

export const inBbox = (bb, lat, lon) => lat >= bb[0][0] && lat <= bb[1][0] && lon >= bb[0][1] && lon <= bb[1][1]

export const fmt = (n) => Math.round(n).toLocaleString('en-US')
export const fmtSec = (ms) => `${(ms / 1000).toFixed(2)} s`

export function fmtMin(sec) {
  const m = Math.round(sec / 60)
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${m % 60} min`
}

export function fmtPct(p) {
  return p >= 10 ? `${p.toFixed(0)}%` : p >= 1 ? `${p.toFixed(1)}%` : `${p.toFixed(2)}%`
}

/* bar width on a log scale: 0.01% -> 5%, 100% -> 100% */
export function barWidth(p) {
  const x = Math.min(100, Math.max(0.01, p))
  return 5 + (95 * (Math.log10(x) + 2)) / 4
}

/* N = n! * C(n+k-1, k-1) */
export function planCount(k, n) {
  if (k < 1 || n < 1) return 0
  let f = 1
  for (let i = 2; i <= n; i++) f *= i
  let c = 1
  for (let i = 1; i <= k - 1; i++) c = (c * (n + i)) / i
  return f * Math.round(c)
}
