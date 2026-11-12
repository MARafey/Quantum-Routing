export const METHODS = [
  { key: 'brute', name: 'Brute force', color: '#7c5e3c' },
  { key: 'parallel', name: 'Parallel', color: '#0b7a69' },
  { key: 'quantum', name: 'Quantum (simulated)', color: '#3451c6' },
]

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
