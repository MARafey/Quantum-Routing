import { useCallback, useEffect, useRef, useState } from 'react'
import RaceMap from './RaceMap.jsx'
import Study from './Study.jsx'
import { METHODS, ROUTE, fmtMin, fmtMs, plural, stopLetter } from './theme.js'
import './App.css'

/* Playback storyboard
   act1  the race: each solver's replay length is proportional to its measured wall-clock time;
         the slowest takes RACE_MS
   act2  how each chose the visit order, equal length so it can be read
   act3  the chosen route draws itself                                                     */
const RACE_MS = 6500
const ORDER_MS = 3200
const ROUTE_MS = 1400
const SPINNER_DELAY_MS = 300

const EXAMPLE = ['Saddar', 'Gulshan', 'North Nazimabad', 'Malir', 'Jauhar', 'Sohrab Goth']

function placeName(places, lat, lon) {
  let best = null, bd = Infinity
  for (const p of places) {
    const d = Math.hypot(p.lat - lat, (p.lon - lon) * 0.91)
    if (d < bd) { bd = d; best = p }
  }
  return bd < 0.014 ? best.name : `${lat.toFixed(4)}, ${lon.toFixed(4)}`
}

function Results({ result }) {
  const best = result.best_cost
  const rows = METHODS.map((m) => ({ m, r: result[m.key] }))
  const fastest = Math.min(...rows.map((x) => x.r.total_ms))
  const work = (key, r) => key === 'brute' ? plural(r.order.evaluated, 'order')
    : key === 'parallel' ? plural(r.order.evaluated, 'DP state')
    : r.order.N > 1 ? plural(r.order.queries_to_min ?? 0, 'query').replace('querys', 'queries') : '–'
  return (
    <div className="results">
      <table>
        <thead><tr><th /><th>Time</th><th>Nodes</th><th>Order work</th><th>Drive</th></tr></thead>
        <tbody>
          {rows.map(({ m, r }) => (
            <tr key={m.key}>
              <td><span className="swatch" style={{ background: m.color }} />{m.short}</td>
              <td className={r.total_ms === fastest ? 'win' : ''}>{fmtMs(r.total_ms)}</td>
              <td>{(r.settled / 1000).toFixed(0)}k</td>
              <td>{work(m.key, r)}</td>
              <td>{r.optimal ? fmtMin(r.order.cost) : <span className="miss">{fmtMin(r.order.cost)}</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {result.orders > 1 ? <p className="note">
        All three return the same {fmtMin(best)} route. Parallel search is fastest on this CPU. The quantum time is a
        classical simulation of {result.quantum.order.qubits} qubits; what it shows is the work: Grover held the best
        of {result.orders.toLocaleString()} orders after {result.quantum.order.queries_to_min ?? '–'} oracle queries,
        where brute force checks all {result.orders.toLocaleString()}.
      </p> : <p className="note">With a single destination there is no visit order to choose, so this compares only the road searches. Add more stops to give the quantum stage work.</p>}
    </div>
  )
}

function Itinerary({ result, stops }) {
  const perm = result.parallel.order.perm
  const seq = [0, ...perm, ...(result.return_to_start ? [0] : [])]
  return (
    <ol className="itinerary">
      {seq.map((s, i) => (
        <li key={i}>
          <span className={`tag${s === 0 ? ' depot' : ''}`}>{stopLetter(s)}</span>
          <span className="it-name">{stops[s]?.name}</span>
          {i > 0 && <span className="it-leg">+{fmtMin(result.leg_cost[seq[i - 1]][s])}</span>}
        </li>
      ))}
    </ol>
  )
}

function Router({ info }) {
  const [stops, setStops] = useState([])
  const [ret, setRet] = useState(false)
  const [result, setResult] = useState(null)
  const [phase, setPhase] = useState('idle') // idle | solving | playing | done
  const [slow, setSlow] = useState(false)
  const [error, setError] = useState('')
  const maps = useRef({})
  const syncing = useRef(false)
  const raf = useRef(0)
  const places = info?.places ?? []
  const max = info?.max_stops ?? 7
  const busy = phase === 'solving' || phase === 'playing'

  useEffect(() => { METHODS.forEach((m) => maps.current[m.key]?.setStops(stops)) }, [stops])

  const addStop = useCallback((lat, lon, name) => {
    setStops((s) => (s.length >= max ? s : [...s, { lat, lon, name: name ?? placeName(places, lat, lon) }]))
    setResult(null); setPhase('idle'); setError('')
    METHODS.forEach((m) => maps.current[m.key]?.clear())
  }, [max, places])

  const onMapClick = useCallback((ll) => { if (!busy) addStop(ll.lat, ll.lng) }, [addStop, busy])
  const onMove = useCallback((key, c, z) => {
    if (syncing.current) return
    syncing.current = true
    METHODS.forEach((m) => { if (m.key !== key) maps.current[m.key]?.syncTo(c, z) })
    syncing.current = false
  }, [])

  const removeStop = (i) => { setStops((s) => s.filter((_, j) => j !== i)); setResult(null); setPhase('idle'); METHODS.forEach((m) => maps.current[m.key]?.clear()) }
  const loadExample = () => {
    const s = EXAMPLE.map((n) => places.find((p) => p.name === n)).filter(Boolean).map((p) => ({ lat: p.lat, lon: p.lon, name: p.name }))
    setStops(s); setResult(null); setPhase('idle'); setError('')
    METHODS.forEach((m) => { maps.current[m.key]?.clear(); maps.current[m.key]?.fit(s) })
  }

  const play = (data) => {
    cancelAnimationFrame(raf.current)
    const slowest = Math.max(...METHODS.map((m) => data[m.key].total_ms))
    const order = [...METHODS].sort((a, b) => data[a.key].total_ms - data[b.key].total_ms)
    const rank = Object.fromEntries(order.map((m, i) => [m.key, ['1st', '2nd', '3rd'][i]]))
    const T = { scale: RACE_MS / slowest, act1: RACE_MS, act2: ORDER_MS, act3: ROUTE_MS, rank }
    METHODS.forEach((m) => maps.current[m.key].load(data[m.key], data))
    const end = T.act1 + T.act2 + T.act3
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce) { METHODS.forEach((m) => maps.current[m.key].frame(end, T)); setPhase('done'); return }
    setPhase('playing')
    const t0 = performance.now()
    const tick = (now) => {
      const t = Math.min(end, now - t0)
      METHODS.forEach((m) => maps.current[m.key].frame(t, T))
      if (t < end) raf.current = requestAnimationFrame(tick)
      else setPhase('done')
    }
    raf.current = requestAnimationFrame(tick)
  }

  const run = async () => {
    if (stops.length < 2 || busy) return
    setPhase('solving'); setError(''); setResult(null)
    const timer = setTimeout(() => setSlow(true), SPINNER_DELAY_MS)
    METHODS.forEach((m) => { maps.current[m.key].clear(); maps.current[m.key].fit(stops) })
    try {
      const r = await fetch('/api/solve', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stops: stops.map(({ lat, lon }) => ({ lat, lon })), return_to_start: ret }),
      })
      if (!r.ok) throw new Error((await r.json()).detail?.toString() || r.statusText)
      const data = await r.json()
      setResult(data)
      play(data)
    } catch (e) {
      setError(`Could not plan the route: ${e.message}. Is the backend running (uv run qroute-server)?`)
      setPhase('idle')
    } finally {
      clearTimeout(timer); setSlow(false)
    }
  }

  return (
    <div className="router">
      <aside className="panel">
        <div className="brand">
          <h1>Convoy router</h1>
          <p className="sub">Relief convoy planning on Karachi's real road network: {info ? `${info.nodes.toLocaleString()} OSM road nodes` : 'loading…'}</p>
        </div>

        <section className="block">
          <div className="block-head">
            <h2>Stops</h2>
            <span className="muted">{stops.length}/{max}</span>
          </div>
          {stops.length === 0 && (
            <p className="empty">Click any map to place the depot <span className="tag depot">A</span>, then each shelter the convoy must reach. The solvers choose the order.</p>
          )}
          <ol className="stops">
            {stops.map((s, i) => (
              <li key={i}>
                <span className={`tag${i === 0 ? ' depot' : ''}`}>{stopLetter(i)}</span>
                <span className="stop-name">{s.name}<small>{i === 0 ? 'Depot (start)' : 'Delivery stop'}</small></span>
                <button className="icon-btn" aria-label={`Remove stop ${stopLetter(i)}`} disabled={busy} onClick={() => removeStop(i)}>
                  <svg viewBox="0 0 16 16" width="14" height="14"><path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
                </button>
              </li>
            ))}
          </ol>
          <div className="row">
            <select aria-label="Add a Karachi place" value="" disabled={busy || stops.length >= max}
              onChange={(e) => { const p = places.find((x) => x.name === e.target.value); if (p) addStop(p.lat, p.lon, p.name) }}>
              <option value="">Add a place…</option>
              {places.map((p) => <option key={p.name} value={p.name}>{p.name}{p.kind === 'shelter' ? ' (shelter)' : ''}</option>)}
            </select>
            <button className="text-btn" disabled={busy} onClick={loadExample}>Use example</button>
          </div>
          <label className="check"><input type="checkbox" checked={ret} disabled={busy} onChange={(e) => setRet(e.target.checked)} /> Return to depot</label>
        </section>

        <button className="primary" disabled={stops.length < 2 || busy} onClick={run}>
          {phase === 'solving' && slow ? 'Running three solvers…' : phase === 'playing' ? 'Replaying…' : result ? 'Plan again' : 'Plan route'}
        </button>
        {stops.length === 1 && <p className="hint">Add at least one more stop.</p>}
        {error && <p className="error" role="alert">{error}</p>}

        {result && (
          <section className={`block reveal${phase === 'done' ? ' on' : ''}`}>
            <h2>Route</h2>
            <Itinerary result={result} stops={stops} />
            <h2>Comparison</h2>
            <Results result={result} />
            <button className="text-btn" onClick={() => play(result)} disabled={phase === 'playing'}>Replay</button>
          </section>
        )}
      </aside>

      <main className="races">
        {METHODS.map((m, i) => (
          <RaceMap key={m.key} method={m} ref={(r) => { maps.current[m.key] = r }} onMapClick={onMapClick}
            onMove={onMove} attribution={i === METHODS.length - 1} />
        ))}
        <div className="legend">
          <span><i className="dot" />searched road nodes</span>
          <span><i className="ln faint" />order being checked</span>
          <span><i className="ln" />best so far</span>
          <span><i className="ln" style={{ background: ROUTE }} />chosen route</span>
        </div>
      </main>
    </div>
  )
}

export default function App() {
  const [view, setView] = useState('router')
  const [info, setInfo] = useState(null)
  useEffect(() => { fetch('/api/info').then((r) => r.json()).then(setInfo).catch(() => setInfo(null)) }, [])
  return (
    <>
      <nav className="views">
        <button className={view === 'router' ? 'on' : ''} onClick={() => setView('router')}>Convoy router</button>
        <button className={view === 'study' ? 'on' : ''} onClick={() => setView('study')}>Evacuation QAOA study</button>
      </nav>
      {view === 'router' ? <Router info={info} /> : <Study />}
    </>
  )
}
