import { METHODS } from './theme.js'
import { fmtBig } from './countryUtil.js'

const col = Object.fromEntries(METHODS.map((m) => [m.key, m.color]))
const AX = '#7b8592', GRID = '#e2e5e9', INK = '#151a21'

/* (a) work to find the best plan, log scale. qFrac in [0,1] animates the quantum bar (scaleX). */
export function WorkBars({ c, qFrac }) {
  const m = c.methods
  const W = m.parallel.workers ?? 8
  const qtm = m.quantum.queries_to_min ?? m.quantum.queries
  const rows = [
    { k: 'brute', name: 'Brute force', v: m.brute.evaluated, label: `${m.brute.evaluated.toLocaleString()} plans` },
    { k: 'parallel', name: 'Parallel classical', v: m.parallel.evaluated, label: `${m.parallel.evaluated.toLocaleString()} plans, over ${W} workers` },
    { k: 'quantum', name: 'Quantum (simulated)', v: qtm, label: `${qtm.toLocaleString()} queries` },
  ]
  const max = Math.log10(Math.max(...rows.map((r) => r.v)) * 1.0) || 1
  const x0 = 130, bw = 245, rowH = 52
  const ticks = [1, 10, 100, 1e3, 1e4, 1e5, 1e6, 1e7].filter((t) => Math.log10(t) <= max + 0.01)
  return (
    <svg viewBox="0 0 580 230" role="img" aria-label="Work to find the best plan, log scale" className="chart">
      {ticks.map((t) => {
        const x = x0 + (Math.log10(t) / max) * bw
        return <g key={t}><line x1={x} x2={x} y1="8" y2="168" stroke={GRID} /><text x={x} y="186" textAnchor="middle" fill={AX} fontSize="11">{fmtBig(t)}</text></g>
      })}
      <text x={x0 + bw / 2} y="212" textAnchor="middle" fill={AX} fontSize="11">Plans checked or oracle queries (log scale)</text>
      {rows.map((r, i) => {
        const y = 14 + i * rowH
        const w = Math.max(2, (Math.log10(Math.max(r.v, 1)) / max) * bw)
        const sx = r.k === 'quantum' ? Math.max(0.001, qFrac) : 1
        return (
          <g key={r.k}>
            <text x={x0 - 10} y={y + 17} textAnchor="end" fill={INK} fontSize="12">{r.name}</text>
            <rect x={x0} y={y} width={w} height="26" rx="2" fill={col[r.k]}
              style={{ transformBox: 'fill-box', transformOrigin: 'left center', transform: `scaleX(${sx})` }} />
            <text x={x0 + w + 8} y={y + 17} fill={INK} fontSize="12" style={{ fontVariantNumeric: 'tabular-nums' }}>{r.label}</text>
          </g>
        )
      })}
    </svg>
  )
}

/* (b) how the work grows with the number of sites */
export function ScalingChart({ c }) {
  const S = c.scaling ?? []
  if (!S.length) return null
  const L = 62, R = 120, T = 14, B = 44, W = 580, H = 230
  const pw = W - L - R, ph = H - T - B
  const nmin = S[0].n, nmax = S[S.length - 1].n
  const ys = S.flatMap((s) => [s.brute_evals, s.heldkarp_states, s.grover_queries].filter((v) => v > 0))
  const lo = Math.floor(Math.log10(Math.min(...ys))), hi = Math.ceil(Math.log10(Math.max(...ys)))
  const X = (n) => L + ((n - nmin) / (nmax - nmin)) * pw
  const Y = (v) => T + ph - ((Math.log10(Math.max(v, 1)) - lo) / (hi - lo)) * ph
  const line = (f) => S.filter((s) => f(s) != null).map((s, i) => `${i ? 'L' : 'M'}${X(s.n).toFixed(1)},${Y(f(s)).toFixed(1)}`).join('')
  const step = Math.ceil((hi - lo) / 5)
  const yt = []
  for (let e = lo; e <= hi; e += step) yt.push(e)
  const last = S[S.length - 1]
  const cur = S.find((s) => s.n === c.n)
  const hk = S.some((s) => s.heldkarp_states != null)
  const lab = (txt, y, color) => <text x={X(nmax) + 8} y={y} fill={color} fontSize="11">{txt}</text>
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Operations needed as the number of sites grows, log scale" className="chart">
      {yt.map((e) => <g key={e}><line x1={L} x2={L + pw} y1={Y(10 ** e)} y2={Y(10 ** e)} stroke={GRID} /><text x={L - 6} y={Y(10 ** e) + 4} textAnchor="end" fill={AX} fontSize="11">{e === 0 ? '1' : `10^${e}`}</text></g>)}
      {[4, 8, 12, 16, 20].filter((n) => n >= nmin && n <= nmax).map((n) => <text key={n} x={X(n)} y={H - 24} textAnchor="middle" fill={AX} fontSize="11">{n}</text>)}
      <text x={L + pw / 2} y={H - 6} textAnchor="middle" fill={AX} fontSize="11">Number of sites to visit</text>
      <text transform={`translate(12 ${T + ph / 2}) rotate(-90)`} textAnchor="middle" fill={AX} fontSize="11">Operations (log scale)</text>
      {cur && <line x1={X(cur.n)} x2={X(cur.n)} y1={T} y2={T + ph} stroke={INK} strokeDasharray="2 3" />}
      <path d={line((s) => s.brute_evals)} fill="none" stroke={col.brute} strokeWidth="2" />
      {hk && <path d={line((s) => s.heldkarp_states)} fill="none" stroke="#7b8592" strokeWidth="1.5" strokeDasharray="5 3" />}
      <path d={line((s) => s.grover_queries)} fill="none" stroke={col.quantum} strokeWidth="2" />
      {cur && [cur.brute_evals, cur.grover_queries].map((v, i) => <circle key={i} cx={X(cur.n)} cy={Y(v)} r="4" fill={i ? col.quantum : col.brute} stroke="#fff" strokeWidth="1.5" />)}
      {cur && <text x={X(cur.n) - 6} y={T + 10} textAnchor="end" fill={INK} fontSize="11">This case: {cur.n} sites</text>}
      {lab('Brute force', Y(last.brute_evals) + 4, col.brute)}
      {hk && lab('Held–Karp (1 convoy)', Y(last.heldkarp_states) + 4, '#49525f')}
      {lab('Grover', Y(last.grover_queries) + 4, col.quantum)}
      <text x={X(nmax) - 4} y={(Y(last.brute_evals) + Y(last.grover_queries)) / 2 + 4} textAnchor="end" fill={INK} fontSize="11" fontWeight="600">{fmtBig(last.brute_evals)} vs {fmtBig(last.grover_queries)}</text>
    </svg>
  )
}
