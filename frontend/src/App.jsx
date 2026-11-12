import { useEffect, useMemo, useRef, useState } from 'react'
import PlanMap from './PlanMap.jsx'
import { METHODS, barWidth, fmt, fmtMin, fmtPct, fmtSec, planCount } from './theme.js'
import './App.css'

const MAX_HUBS = 3
const MAX_SITES = 10
const MAX_PLANS = 4_000_000
const BUSY_LABEL_DELAY_MS = 300

async function api(path, body) {
  const res = await fetch(path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : undefined)
  if (!res.ok) {
    let detail = res.statusText
    try { const j = await res.json(); detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail) } catch { /* keep statusText */ }
    const e = new Error(detail); e.http = res.status; throw e
  }
  return res.json()
}

// In dev only, fall back to a local mock if the backend is unreachable (network error or bare 5xx).
async function call(path, body) {
  try { return await api(path, body) } catch (e) {
    if (import.meta.env.DEV && (!e.http || e.http >= 500 || e.http === 404)) {
      const m = await import('./mock.js')
      return path === '/api/random' ? m.mockRandom() : m.mockRun(body)
    }
    throw e
  }
}

const Close = () => <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>

function Results({ r }) {
  const q = r.methods.quantum
  const reduction = q.coverage_pct > 0 ? Math.round(100 / q.coverage_pct) : null
  const rows = METHODS.map((m) => ({ m, d: r.methods[m.key] }))
  const work = (key, d) => key === 'quantum' ? `${fmt(d.queries_to_min ?? d.queries)} queries to the best plan` : `${fmt(d.evaluated)} plans`
  return (
    <section className="results" aria-label="Results">
      <p className="rhead">N = {fmt(r.N)} possible plans · {r.n} stops + {r.k} {r.k === 1 ? 'hub' : 'hubs'}</p>
      {rows.map(({ m, d }) => (
        <div className={`mrow${m.key === 'quantum' ? ' hero' : ''}`} key={m.key}>
          <div className="mtop">
            <span className="mname"><i style={{ background: m.color }} />{m.name}{!d.optimal && <em className="miss">not optimal</em>}</span>
            <span className="mtime num">{fmtSec(d.ms)}</span>
          </div>
          <div className="cov">
            <div className="bar"><div style={{ width: `${barWidth(d.coverage_pct)}%`, background: m.color }} /></div>
            <span className="num">{fmtPct(d.coverage_pct)} of plans</span>
          </div>
          <div className="work num">{work(m.key, d)}{m.key === 'quantum' && reduction > 1 ? ` · ${fmt(reduction)}× less search` : ''}</div>
        </div>
      ))}
      <p className="best">Best plan: last site reached in {fmtMin(r.best.makespan_s)}</p>
      <p className="note">Quantum time is a CPU simulation; coverage = share of all plans examined before the best plan was found.</p>
    </section>
  )
}

export default function App() {
  const [hubs, setHubs] = useState([])
  const [sites, setSites] = useState([])
  const [mode, setMode] = useState('site')
  const [result, setResult] = useState(null)
  const [playback, setPlayback] = useState(null)
  const [running, setRunning] = useState(false)
  const [label, setLabel] = useState(false)
  const [rolling, setRolling] = useState(false)
  const [error, setError] = useState('')
  const counter = useRef(0)

  const N = useMemo(() => planCount(hubs.length, sites.length), [hubs, sites])
  const tooMany = N > MAX_PLANS
  const canRun = hubs.length >= 1 && sites.length >= 2 && !tooMany && !running
  const canAdd = !running && (mode === 'hub' ? hubs.length < MAX_HUBS : sites.length < MAX_SITES)

  const reset = () => { setResult(null); setPlayback(null); setError('') }

  const add = (lat, lon) => {
    reset()
    const p = { name: `Point ${++counter.current}`, lat, lon }
    if (mode === 'hub') setHubs((h) => [...h, p]); else setSites((s) => [...s, p])
  }
  const remove = (kind, i) => { if (running) return; reset(); (kind === 'hub' ? setHubs : setSites)((l) => l.filter((_, j) => j !== i)) }
  const clear = () => { if (running) return; reset(); setHubs([]); setSites([]); counter.current = 0 }
  const random = async () => {
    if (running || rolling) return
    setRolling(true); reset()
    try { const d = await call('/api/random'); setHubs(d.hubs); setSites(d.sites) } catch (e) { setError(e.message) }
    setRolling(false)
  }
  const run = async () => {
    if (!canRun) return
    setRunning(true); setLabel(false); reset()
    const t = setTimeout(() => setLabel(true), BUSY_LABEL_DELAY_MS)
    try {
      const r = await call('/api/run', { hubs, sites, return_to_depot: false })
      setResult(r); setPlayback({ result: r, id: Date.now() })
    } catch (e) { setError(e.message || 'Run failed') }
    clearTimeout(t); setRunning(false); setLabel(false)
  }

  useEffect(() => { document.title = 'Relief convoy planner' }, [])

  const stopRow = (kind, p, i) => (
    <li key={`${kind}${i}`}>
      <span className={`tag ${kind}`}>{kind === 'hub' ? String.fromCharCode(65 + i) : i + 1}</span>
      <span className="sname">{p.name}</span>
      <button className="icon-btn" aria-label={`Remove ${p.name}`} disabled={running} onClick={() => remove(kind, i)}><Close /></button>
    </li>
  )

  return (
    <div className="app">
      <aside className="side">
        <header>
          <h1>Relief convoy planner</h1>
          <p className="sub">Pakistan · brute force vs parallel vs quantum search</p>
        </header>

        <section className="stops">
          <div className="seg-wrap">
            <span className="seg-label" id="addlbl">Click map to add</span>
            <div className="seg" role="radiogroup" aria-labelledby="addlbl">
              {['hub', 'site'].map((m) => (
                <button key={m} role="radio" aria-checked={mode === m} className={mode === m ? 'on' : ''} onClick={() => setMode(m)}>{m === 'hub' ? 'Hub' : 'Site'}</button>
              ))}
            </div>
          </div>
          <div className="actions">
            <button className="secondary" onClick={random} disabled={running || rolling}>Random stops</button>
            <button className="text-btn" onClick={clear} disabled={running || (!hubs.length && !sites.length)}>Clear</button>
          </div>
          {(hubs.length > 0 || sites.length > 0) ? (
            <ul className="list">{hubs.map((p, i) => stopRow('hub', p, i))}{sites.map((p, i) => stopRow('site', p, i))}</ul>
          ) : <p className="empty">Hubs are convoy start points (up to {MAX_HUBS}); sites are stops to reach (up to {MAX_SITES}).</p>}
          {N > 0 && <p className={`plans num${tooMany ? ' bad' : ''}`}>{tooMany ? 'Too many plans for this demo — remove a stop' : `${fmt(N)} possible plans`}</p>}
        </section>

        <div>
          <button className={`run${running ? ' busy' : ''}`} onClick={run} disabled={!canRun}>{running && label ? 'Running…' : 'Run'}</button>
          {error && <p className="error" role="alert">{error}</p>}
        </div>

        {result && <Results r={result} key={playback?.id} />}
      </aside>
      <PlanMap hubs={hubs} sites={sites} mode={mode} canAdd={canAdd} onAdd={add} playback={playback} />
    </div>
  )
}
