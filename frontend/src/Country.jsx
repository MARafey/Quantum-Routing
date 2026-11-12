import { useCallback, useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { METHODS, fmtMin, fmtMs, stopLetter } from './theme.js'
import { CONVOY, bestUpTo, clamp01, easeInOut, loadCase, loadIndex, routeCoords } from './countryUtil.js'
import { ScalingChart, WorkBars } from './CountryCharts.jsx'
import './Country.css'

/* Playback storyboard (the data is precomputed; this replays it)
   act 1  "Quantum search": step through the quantum samples by query number. The measured plan is drawn
          faintly, the best plan so far solid, and a counter and the quantum work bar grow with the queries.
   act 2  the optimal routes draw progressively in convoy colours                                       */
const ACT1_MS = 5000
const ACT2_MS = 1400
const END_MS = ACT1_MS + ACT2_MS

const IDLE = { act: 0, qi: -1, p: 0 }
const DONE = (n) => ({ act: 2, qi: n - 1, p: 1 })
const NAMES = { brute: 'Brute force', parallel: 'Parallel classical', quantum: 'Quantum (simulated)' }

function Panel({ list, mock, sel, onSel, c, phase, onRun, loading }) {
  const m = c?.methods
  const qtm = m && (m.quantum.queries_to_min ?? m.quantum.queries)
  const rows = m && [
    { k: 'brute', r: m.brute, work: `${m.brute.evaluated.toLocaleString()} plans` },
    { k: 'parallel', r: m.parallel, work: `${m.parallel.evaluated.toLocaleString()} plans` },
    { k: 'quantum', r: m.quantum, work: `${qtm.toLocaleString()} queries` },
  ]
  const busy = phase === 'playing'
  return (
    <aside className="panel">
      <div className="brand">
        <h1>Country-scale relief</h1>
        <p className="sub">Several convoys, many sites: the number of possible plans explodes.</p>
      </div>
      <div className="cases" role="radiogroup" aria-label="Disaster case">
        {list.map((x) => (
          <button key={x.id} type="button" role="radio" aria-checked={x.id === sel} className="case" onClick={() => onSel(x.id)}>
            <span className="case-title">{x.title}</span>
            <span className="case-region">{x.region} · {x.k} {x.k === 1 ? 'convoy' : 'convoys'}, {x.n} sites</span>
            <span className="case-n">{x.N.toLocaleString()} <small>possible plans · {x.qubits} qubits</small></span>
          </button>
        ))}
      </div>
      {mock && <p className="hint">Showing placeholder data until the case files are generated.</p>}
      {c && <p className="story">{c.story}</p>}
      <div className="actions">
        <button type="button" className="primary" disabled={!c || busy || loading} onClick={() => onRun()}>{busy ? 'Replaying…' : 'Run comparison'}</button>
        <button type="button" className="text-btn" disabled={!c || busy || phase === 'idle'} onClick={() => onRun()}>Replay</button>
      </div>
      <p className="hint">Results are precomputed; the run replays them.</p>
      {c && (
        <section className="block">
          <table className="ctable">
            <thead><tr><th /><th>Time</th><th>Work</th><th>Makespan</th><th>Optimal</th></tr></thead>
            <tbody>
              {rows.map(({ k, r, work }) => (
                <tr key={k}>
                  <td><span className="swatch" style={{ background: METHODS.find((x) => x.key === k).color }} />{NAMES[k]}</td>
                  <td>{fmtMs(r.ms)}</td><td>{work}</td>
                  <td>{fmtMin(r.solution.makespan_s)}</td>
                  <td>{r.optimal ? 'Optimal' : <span className="miss">Not optimal</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="callout">Quantum held the best plan after {qtm.toLocaleString()} queries — {Math.round(c.N / qtm).toLocaleString()}× fewer than brute force's {c.N.toLocaleString()} evaluations.</p>
          {m.quantum.break_even_us != null && (
            <p className="note">On quantum hardware this wins if one oracle query takes less than {Number(m.quantum.break_even_us).toLocaleString(undefined, { maximumFractionDigits: 1 })} µs (vs this CPU's brute force).</p>
          )}
          <p className="note small">Quantum timings are a classical simulation (backend "{m.quantum.backend}"; "grover-closed-form" is exact Grover measurement statistics, verified against Qiskit circuits at small sizes). Held–Karp DP is the best exact classical method for one convoy and overtakes Grover beyond about 20 sites. Error-correction overheads may erase quadratic speedups (Babbush et al. 2021).</p>
        </section>
      )}
    </aside>
  )
}

function MapPane({ c, frame, phase }) {
  const el = useRef(null)
  const g = useRef({})
  const cache = useRef({ id: null })
  useEffect(() => {
    const map = L.map(el.current, { zoomControl: true, zoomSnap: 0.25 }).setView([27, 68], 6)
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '© OpenStreetMap contributors', maxZoom: 18 }).addTo(map)
    g.current = { map, cand: L.layerGroup().addTo(map), best: L.layerGroup().addTo(map), fin: L.layerGroup().addTo(map), mk: L.layerGroup().addTo(map) }
    return () => map.remove()
  }, [])
  useEffect(() => {
    const { map, mk } = g.current
    mk.clearLayers()
    if (!c) return
    c.points.forEach((p, i) => {
      const depot = i < c.k
      const html = `<div class="tag${depot ? ' depot' : ''}">${depot ? stopLetter(i) : i - c.k + 1}</div>`
      L.marker([p.lat, p.lon], { icon: L.divIcon({ className: '', html, iconSize: [22, 22], iconAnchor: [11, 11] }), interactive: false, keyboard: false, title: p.name }).addTo(mk)
    })
    map.invalidateSize()
    map.fitBounds(L.latLngBounds(c.points.map((p) => [p.lat, p.lon])).pad(0.2), { animate: false })
  }, [c])
  useEffect(() => {
    const { cand, best, fin } = g.current
    if (!c) return
    if (cache.current.id !== c.id) cache.current = { id: c.id, final: c.methods.quantum.solution.routes.map((r) => routeCoords(c, r)) }
    const S = c.methods.quantum.samples
    cand.clearLayers(); best.clearLayers(); fin.clearLayers()
    if (frame.act === 1 && frame.qi >= 0) {
      S[frame.qi].solution.routes.forEach((r, i) => L.polyline(routeCoords(c, r), { color: CONVOY[i % CONVOY.length], weight: 3, opacity: 0.35 }).addTo(cand))
      bestUpTo(S, frame.qi).solution.routes.forEach((r, i) => L.polyline(routeCoords(c, r), { color: CONVOY[i % CONVOY.length], weight: 4, opacity: 0.95 }).addTo(best))
    }
    if (frame.act === 2) {
      const e = easeInOut(clamp01(frame.p))
      cache.current.final.forEach((co, i) => {
        const n = Math.max(2, Math.ceil(co.length * e))
        L.polyline(co.slice(0, n), { color: CONVOY[i % CONVOY.length], weight: 5, opacity: 0.95, lineCap: 'round' }).addTo(fin)
      })
    }
  }, [c, frame])
  const S = c?.methods.quantum.samples
  const smp = c && frame.act === 1 && frame.qi >= 0 ? S[frame.qi] : null
  const bst = smp ? bestUpTo(S, frame.qi) : null
  return (
    <div className="map-wrap">
      <div ref={el} className="map" />
      {smp && <div className="counter">query {smp.q.toLocaleString()} / {c.methods.quantum.queries.toLocaleString()} · best makespan {fmtMin(bst.cost_s)}</div>}
      {c && phase === 'done' && <div className="counter">Best plan: makespan {fmtMin(c.methods.quantum.solution.makespan_s)}</div>}
      {c && (
        <div className="mlegend">
          {Array.from({ length: c.k }, (_, i) => <span key={i}><i style={{ background: CONVOY[i % CONVOY.length] }} />Convoy {stopLetter(i)}</span>)}
          <span className="faint"><i />Plan measured now</span>
        </div>
      )}
    </div>
  )
}

export default function Country() {
  const [idx, setIdx] = useState({ list: [], mock: false })
  const [sel, setSel] = useState(null)
  const [c, setC] = useState(null)
  const [loading, setLoading] = useState(true)
  const [frame, setFrame] = useState(IDLE)
  const [phase, setPhase] = useState('idle')
  const raf = useRef(0)

  useEffect(() => { loadIndex().then((r) => { setIdx(r); setSel(r.list[0].id) }).catch(() => setLoading(false)) }, [])
  useEffect(() => {
    if (!sel) return
    cancelAnimationFrame(raf.current)
    setFrame(IDLE); setPhase('idle'); setLoading(true)
    loadCase(sel).then((d) => { setC(d); setLoading(false) }).catch(() => { setC(null); setLoading(false) })
  }, [sel])
  useEffect(() => () => cancelAnimationFrame(raf.current), [])

  const run = useCallback(() => {
    if (!c) return
    cancelAnimationFrame(raf.current)
    const n = c.methods.quantum.samples.length
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { setFrame(DONE(n)); setPhase('done'); return }
    setPhase('playing')
    const t0 = performance.now()
    const tick = (now) => {
      const t = Math.min(END_MS, now - t0)
      if (t < ACT1_MS) setFrame({ act: 1, qi: Math.min(n - 1, Math.floor((t / ACT1_MS) * n)), p: 0 })
      else setFrame({ act: 2, qi: n - 1, p: (t - ACT1_MS) / ACT2_MS })
      if (t < END_MS) raf.current = requestAnimationFrame(tick)
      else setPhase('done')
    }
    raf.current = requestAnimationFrame(tick)
  }, [c])

  const q = c?.methods.quantum
  const qtm = q && (q.queries_to_min ?? q.queries)
  const animating = q && frame.act === 1 && frame.qi >= 0
  const cur = animating ? Math.min(q.samples[frame.qi].q, qtm) : qtm
  const qFrac = animating ? Math.log10(cur + 1) / Math.log10(qtm + 1) : 1
  return (
    <div className="country">
      <Panel list={idx.list} mock={idx.mock} sel={sel} onSel={setSel} c={c} phase={phase} onRun={run} loading={loading} />
      <main className="cmain">
        <MapPane c={c} frame={frame} phase={phase} />
        <div className="charts">
          <section><h2>Work to find the best plan</h2>{c && <WorkBars c={c} qFrac={qFrac} />}</section>
          <section><h2>As the disaster grows</h2>{c && <ScalingChart c={c} />}</section>
        </div>
      </main>
    </div>
  )
}
