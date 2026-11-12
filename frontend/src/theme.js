export const ROUTE = '#d9480f' // signal orange: the convoy's chosen route

export const METHODS = [
  {
    key: 'brute', name: 'Brute force', short: 'Brute force', color: '#7c5e3c', dot: 'rgba(124, 94, 60, 0.55)',
    how: 'Full Dijkstra from each stop, one after another, then every visit order checked',
    orderVerb: 'Checking every order',
  },
  {
    key: 'parallel', name: 'Parallel classical', short: 'Parallel', color: '#0b7a69', dot: 'rgba(11, 122, 105, 0.55)',
    how: 'Bounded Dijkstra from all stops at once on worker processes, then Held–Karp',
    orderVerb: 'Held–Karp DP',
  },
  {
    key: 'quantum', name: 'Quantum (simulated)', short: 'Quantum', color: '#3451c6', dot: 'rgba(52, 81, 198, 0.55)',
    how: 'Same parallel road search, then Grover minimum search over visit orders in Qiskit',
    orderVerb: 'Grover search (simulator)',
  },
]

export const plural = (n, w) => `${n.toLocaleString()} ${w}${n === 1 ? '' : 's'}`

export const stopLetter = (i) => String.fromCharCode(65 + i)

export function fmtMs(ms) {
  return `${(ms / 1000).toFixed(2)} s`
}

export function fmtMin(sec) {
  const m = sec / 60
  return m < 60 ? `${m.toFixed(1)} min` : `${Math.floor(m / 60)} h ${Math.round(m % 60)} min`
}
