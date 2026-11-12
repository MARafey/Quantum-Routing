import { useEffect, useMemo, useRef, useState } from 'react'
import PlanMap from './PlanMap.jsx'
import { METHODS, PAKISTAN, barWidth, fmt, fmtMin, fmtPct, fmtSec, inBbox, normBbox, planCount } from './theme.js'
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
      if (path.startsWith('/api/regions')) return m.mockRegions()
      return path.startsWith('/api/random') ? m.mockRandom(path) : m.mockRun(body)
    }
    throw e
  }
}

const Close = () => <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>

function workLine(key, d) {
  if (key === 'quantum_ws') return `${fmt(d.queries_to_min ?? d.queries)} queries + ${fmt(d.heuristic_evals ?? 0)} heuristic evals`
  if (key === 'quantum') return `${fmt(d.queries_to_min ?? d.queries)} queries to the best plan`
  return `${fmt(d.evaluated)} plans`
}

function Results({ r }) {
  const bruteCov = r.methods.brute?.coverage_pct ?? 100
  const rows = Object.keys(METHODS).filter((k) => r.methods[k]).map((k) => ({ m: METHODS[k], d: r.methods[k] }))
    .sort((a, b) => a.d.coverage_pct - b.d.coverage_pct || a.d.ms - b.d.ms)
  return (
    <section className="results" aria-label="Results">
      <p className="rhead">N = {fmt(r.N)} possible plans · {r.n} stops + {r.k} {r.k === 1 ? 'hub' : 'hubs'}</p>
      {rows.map(({ m, d }, i) => {
        const q = m.key.startsWith('quantum')
        const reduction = q && d.coverage_pct > 0 ? Math.round(bruteCov / d.coverage_pct) : null
        return (
          <div className={`mrow${q ? ' q' : ''}`} key={m.key}>
            <div className="mtop">
              <span className="mname"><b className="rank num">{i + 1}.</b><i style={{ background: m.color }} />{m.name}{!d.optimal && <em className="miss">not optimal</em>}</span>
              <span className="mtime num">{fmtSec(d.ms)}</span>
            </div>
            <div className="cov">
              <div className="bar"><div style={{ width: `${barWidth(d.coverage_pct)}%`, background: m.color }} /></div>
              <span className="num">{fmtPct(d.coverage_pct)} of plans</span>
            </div>
            <div className="work num">{workLine(m.key, d)}{reduction > 1 ? ` · ${fmt(reduction)}× less search` : ''}</div>
          </div>
        )
      })}
      <p className="best">Best plan: last site reached in {fmtMin(r.best.makespan_s)}</p>
      <p className="note">Ranked by share of plans examined. Quantum times are a CPU simulation of the quantum search.</p>
    </section>
  )
}

export default function App() {
  const [hubs, setHubs] = useState([])
  const [sites, setSites] = useState([])
  const [mode, setMode] = useState('site')
  const [scope, setScope] = useState('pk')
  const [regions, setRegions] = useState(undefined) // undefined = loading, null = unavailable
  const [regionId, setRegionId] = useState('')
  const [result, setResult] = useState(null)
  const [playback, setPlayback] = useState(null)
  const [running, setRunning] = useState(false)
  const [rolling, setRolling] = useState(false)
  const [error, setError] = useState('')
  const [hint, setHint] = useState('')
  const counter = useRef(0)

  useEffect(() => {
    let live = true
    call('/api/regions').then((d) => {
      const list = (Array.isArray(d) ? d : d?.regions || []).map((r) => ({ ...r, bbox: normBbox(r.bbox) })).filter((r) => r.id && r.bbox)
      // "Other regions" lists only regions outside Pakistan; Pakistan has its own scope button.
      const others = list.filter((r) => r.id !== 'pakistan')
      if (live) { setRegions(others.length ? others : null); setRegionId(others[0]?.id || '') }
    }).catch(() => live && setRegions(null))
    return () => { live = false }
  }, [])

  const region = scope === 'pk' ? PAKISTAN : regions?.find((r) => r.id === regionId) || PAKISTAN
  const bbox = region.bbox

  const N = useMemo(() => planCount(hubs.length, sites.length), [hubs, sites])
  const tooMany = N > MAX_PLANS
  const canRun = hubs.length >= 1 && sites.length >= 2 && !tooMany && !running
  const canAdd = !running && (mode === 'hub' ? hubs.length < MAX_HUBS : sites.length < MAX_SITES)

  const reset = () => { setResult(null); setPlayback(null); setError(''); setHint('') }
  const wipe = () => { reset(); setHubs([]); setSites([]); counter.current = 0 }

  const pickScope = (s) => { if (running || s === scope) return; wipe(); setScope(s) }
  const pickRegion = (id) => { if (running) return; wipe(); setRegionId(id) }

  const add = (lat, lon) => {
    if (!inBbox(bbox, lat, lon)) { setHint(`Outside ${region.name}. Click inside the highlighted area.`); return }
    reset()
    const p = { name: `Point ${++counter.current}`, lat, lon }
    if (mode === 'hub') setHubs((h) => [...h, p]); else setSites((s) => [...s, p])
  }
  const remove = (kind, i) => { if (running) return; reset(); (kind === 'hub' ? setHubs : setSites)((l) => l.filter((_, j) => j !== i)) }
  const clear = () => { if (running) return; wipe() }
  const random = async () => {
    if (running || rolling) return
    setRolling(true); reset()
    try { const d = await call(`/api/random?region=${encodeURIComponent(region.id)}`); setHubs(d.hubs); setSites(d.sites) } catch (e) { setError(e.message) }
    setRolling(false)
  }
  const run = async () => {
    if (!canRun) return
    setRunning(true); reset()
    try {
      const r = await call('/api/run', { region: region.id, hubs, sites, return_to_depot: false })
      setResult(r); setPlayback({ result: r, id: Date.now() })
    } catch (e) { setError(e.message || 'Run failed') }
    setRunning(false)
  }

  useEffect(() => { document.title = 'Relief convoy planner' }, [])

  const stopRow = (kind, p, i) => (
    <li key={`${kind}${i}`}>
      <span className={`tag ${kind}`}>{kind === 'hub' ? String.fromCharCode(65 + i) : i + 1}</span>
      <span className="sname">{p.name}</span>
      <button className="icon-btn" aria-label={`Remove ${p.name}`} disabled={running} onClick={() => remove(kind, i)}><Close /></button>
    </li>
  )
  const regionsOff = regions === null || regions === undefined

  return (
    <div className="app">
      <aside className="side">
        <header>
          <h1>Relief convoy planner</h1>
        </header>

        <section className="stops">
          <div className="seg full" role="radiogroup" aria-label="Scope">
            <button role="radio" aria-checked={scope === 'pk'} className={scope === 'pk' ? 'on' : ''} disabled={running} onClick={() => pickScope('pk')}>Within Pakistan</button>
            <button role="radio" aria-checked={scope === 'other'} className={scope === 'other' ? 'on' : ''} disabled={running || regionsOff} onClick={() => pickScope('other')}>Other regions</button>
          </div>
          {regions === null && <p className="empty">Regions unavailable</p>}
          {scope === 'other' && regions && (
            <select className="region" aria-label="Region" value={regionId} disabled={running} onChange={(e) => pickRegion(e.target.value)}>
              {regions.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
          )}
          <div className="seg-wrap">
            <span className="seg-label" id="addlbl">Click map to add</span>
            <div className="seg" role="radiogroup" aria-labelledby="addlbl">
              {['hub', 'site'].map((m) => (
                <button key={m} role="radio" aria-checked={mode === m} className={mode === m ? 'on' : ''} onClick={() => setMode(m)}>{m === 'hub' ? 'Hub' : 'Site'}</button>
              ))}
            </div>
          </div>
          {hint && <p className="hint" role="status">{hint}</p>}
          <div className="actions">
            <button className="secondary" onClick={random} disabled={running || rolling}>Random stops</button>
            <button className="text-btn" onClick={clear} disabled={running || (!hubs.length && !sites.length)}>Clear</button>
          </div>
          {(hubs.length > 0 || sites.length > 0) ? (
            <div className="lists">
              {hubs.length > 0 && <><h2 className="sect">Hubs</h2><ul className="list hubs">{hubs.map((p, i) => stopRow('hub', p, i))}</ul></>}
              {sites.length > 0 && <><h2 className="sect">Sites</h2><ul className="list">{sites.map((p, i) => stopRow('site', p, i))}</ul></>}
            </div>
          ) : <p className="empty">Hubs are convoy start points (up to {MAX_HUBS}); sites are stops to reach (up to {MAX_SITES}).</p>}
          {N > 0 && <p className={`plans num${tooMany ? ' bad' : ''}`}>{tooMany ? 'Too many plans for this demo — remove a stop' : `${fmt(N)} possible plans`}</p>}
        </section>

        <div>
          <button className={`run${running ? ' busy' : ''}`} onClick={run} disabled={!canRun}>Run</button>
          {running && <p className="status num" role="status">Searching {fmt(N)} possible plans…</p>}
          {error && <p className="error" role="alert">{error}</p>}
        </div>

        {result && <Results r={result} key={playback?.id} />}
      </aside>
      <PlanMap hubs={hubs} sites={sites} mode={mode} canAdd={canAdd} onAdd={add} playback={playback} searching={running} bbox={bbox} regionKey={region.id} />
    </div>
  )
}
