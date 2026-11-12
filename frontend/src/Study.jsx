import { useEffect, useMemo, useState } from 'react'
import MapView, { GROUP_COLORS } from './MapView.jsx'
import { Bars, LineChart, Histogram } from './Charts.jsx'
import './Study.css'

const fmt = (v, d = 1) => (v === null || v === undefined ? '–' : Number(v).toFixed(d))

function MethodTable({ methods, selected, onSelect }) {
  return (
    <table className="tbl">
      <thead>
        <tr><th>Method</th><th>Objective</th><th>Gap</th><th>Avg travel</th><th>Max bus load</th><th>Overloaded segs</th><th>Shelter overflow</th></tr>
      </thead>
      <tbody>
        {methods.map((m, i) => (
          <tr key={m.method} className={i === selected ? 'sel' : ''} onClick={() => onSelect(i)}>
            <td>{m.method}</td>
            <td>{fmt(m.energy, 0)}</td>
            <td className={m.gap_pct < 1e-6 ? 'good' : 'bad'}>{fmt(m.gap_pct, 2)}%</td>
            <td>{fmt(m.metrics.avg_travel_min)} min</td>
            <td className={m.metrics.max_bus_load_factor > 1 ? 'bad' : ''}>{fmt(100 * m.metrics.max_bus_load_factor, 0)}%</td>
            <td>{m.metrics.overloaded_bus_segments}</td>
            <td>{m.metrics.shelter_overflow}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Assignment({ instance, assignment }) {
  return (
    <div className="assign">
      {assignment.map((r, g) => {
        const o = instance.options[g][r]
        const grp = instance.groups[g]
        return (
          <div key={g} className="assign-row">
            <span className="dot" style={{ background: GROUP_COLORS[g % 12] }} />
            <b>G{g + 1}</b>&nbsp;{grp.origin} ({grp.size}) → {o.shelter}
            <span className="muted">&nbsp;opt {r + 1} · {o.travel_min} min · {o.transfers} xfer · {o.legs.filter((l) => l.kind === 'bus').map((l) => l.line.split(' ')[0]).join('→')}</span>
          </div>
        )
      })}
    </div>
  )
}

function SmallTab({ data, network }) {
  const s = data.small
  const exactIdx = s.methods.findIndex((m) => m.method.startsWith('Exact'))
  const [sel, setSel] = useState(s.methods.length - 1)
  const [showAll, setShowAll] = useState(false)
  const m = s.methods[sel]
  const runs = s.qaoa
  const bestXY = runs.filter((r) => r.variant === 'xy').at(-1)
  const bestPen = runs.filter((r) => r.variant === 'penalty').at(-1)
  return (
    <div className="split">
      <div className="left">
        <MapView network={network} instance={s} assignment={m.assignment} showAllOptions={showAll} />
        <label className="chk"><input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} /> show all RAPTOR journey options (QAOA search space)</label>
      </div>
      <div className="right">
        <h3>12-qubit instance — 4 evacuee groups × 3 RAPTOR journeys</h3>
        <p className="muted">Click a row to draw that method's routes. Exact optimum found by brute force over all {Math.pow(s.K, s.groups.length)} feasible assignments.</p>
        <MethodTable methods={s.methods} selected={sel} onSelect={setSel} />
        <h4>Selected: {m.method}</h4>
        <Assignment instance={s} assignment={m.assignment} />

        <h4>Quantum sampling quality (4096 shots, Aer)</h4>
        <div className="grid2">
          <div>
            <div className="sub">P(feasible sample)</div>
            <Bars rows={runs.map((r) => ({ label: `${r.variant === 'xy' ? 'XY' : 'Penalty'} p=${r.reps}`, value: r.p_feasible, color: r.variant === 'xy' ? '#2563eb' : '#d97706' }))} />
          </div>
          <div>
            <div className="sub">P(optimal sample) · random guess = {fmt(100 / Math.pow(s.K, s.groups.length), 2)}%</div>
            <Bars max={Math.max(...runs.map((r) => r.p_optimal), 0.02)} fmt={(v) => (100 * v).toFixed(1) + '%'}
              rows={runs.map((r) => ({ label: `${r.variant === 'xy' ? 'XY' : 'Penalty'} p=${r.reps}`, value: r.p_optimal, color: r.variant === 'xy' ? '#2563eb' : '#d97706' }))} />
          </div>
        </div>
        <table className="tbl small">
          <thead><tr><th>Run</th><th>Approx. ratio</th><th>Found opt.</th><th>Depth</th><th>CNOTs</th><th>Evals</th><th>Sim time</th></tr></thead>
          <tbody>{runs.map((r) => (
            <tr key={r.variant + r.reps}><td>{r.variant === 'xy' ? 'XY-mixer' : 'Penalty'} p={r.reps}</td><td>{fmt(r.approx_ratio, 3)}</td>
              <td>{r.found_optimum ? '✔' : '✘'}</td><td>{r.circuit_depth}</td><td>{r.cx_count}</td><td>{r.evaluations}</td><td>{fmt(r.seconds)} s</td></tr>
          ))}</tbody>
        </table>
        <div className="grid2">
          <div>
            <div className="sub">Training curve (CVaR loss, best restart)</div>
            <LineChart xLabel="optimizer evaluation" yLabel="loss"
              series={[{ name: `XY p=${bestXY.reps}`, color: '#2563eb', points: bestXY.history.map((v, i) => [i, v]) },
                { name: `Penalty p=${bestPen.reps}`, color: '#d97706', points: bestPen.history.map((v, i) => [i, v]) }]} />
          </div>
          <div>
            <div className="sub">Where solutions sit in the landscape of all {s.landscape.length} feasible assignments</div>
            <Histogram values={s.landscape} marks={[
              { label: 'exact', value: s.exact_energy, color: '#059669', row: 0 },
              { label: 'no coordination', value: s.methods[0].energy, color: '#dc2626', row: 1 },
              { label: 'QAOA E[feasible]', value: bestXY.expected_feasible_energy, color: '#2563eb', row: 2 },
            ]} />
          </div>
        </div>
        <h4>Top measured bitstrings — XY p={bestXY.reps}</h4>
        <table className="tbl small mono">
          <thead><tr><th>bitstring (q11…q0)</th><th>count</th><th>assignment</th><th>objective</th></tr></thead>
          <tbody>{bestXY.top_samples.slice(0, 8).map((t) => (
            <tr key={t.bitstring} className={t.energy !== null && Math.abs(t.energy - s.exact_energy) < 1e-6 ? 'good' : ''}>
              <td>{t.bitstring}</td><td>{t.count}</td><td>{t.assignment ? t.assignment.map((x) => x + 1).join(',') : 'infeasible'}</td><td>{fmt(t.energy, 0)}</td></tr>
          ))}</tbody>
        </table>
        <p className="muted">Exact optimum: {s.methods[exactIdx].assignment.map((x) => x + 1).join(',')} (objective {fmt(s.exact_energy, 0)})</p>
      </div>
    </div>
  )
}

function LargeTab({ data, network }) {
  const L = data.large
  const [sel, setSel] = useState(L.methods.length - 1)
  const m = L.methods[sel]
  return (
    <div className="split">
      <div className="left"><MapView network={network} instance={L} assignment={m.assignment} /></div>
      <div className="right">
        <h3>City-scale instance — 12 groups (two waves) × 3 journeys = 36 binary variables</h3>
        <p className="muted">Too large for one simulated circuit (2³⁶ amplitudes). Groups are clustered by shared buses/shelters into ≤12-qubit sub-problems, each re-optimised with XY-QAOA while the others are fixed (block-coordinate descent). Exact reference: brute force over {Math.pow(3, 12).toLocaleString()} assignments.</p>
        <MethodTable methods={L.methods} selected={sel} onSelect={setSel} />
        <h4>Clusters (by coupling strength)</h4>
        <div className="assign">{L.clusters.map((c, i) => (
          <div key={i} className="assign-row"><b>C{i + 1}</b>&nbsp;{c.map((g) => `G${g + 1} ${L.groups[g].origin}${L.groups[g].dep ? '(wave 2)' : ''}`).join(', ')}</div>
        ))}</div>
        <div className="sub">Objective after each cluster solve (green dashed = exact optimum)</div>
        <LineChart xLabel="cluster solve step" yLabel="objective" series={[
          { name: 'clustered QAOA', color: '#2563eb', points: L.trace.map((t) => [t.step, t.energy]) },
          { name: 'exact', color: '#059669', dash: '5 4', points: L.trace.map((t) => [t.step, L.exact_energy]) },
        ]} />
        <table className="tbl small">
          <thead><tr><th>Step</th><th>Cluster</th><th>Sub-problem P(opt)</th><th>Accepted</th><th>Objective</th></tr></thead>
          <tbody>{L.trace.slice(1).map((t) => (
            <tr key={t.step}><td>{t.step}</td><td>{t.cluster.map((g) => 'G' + (g + 1)).join(' ')}</td><td>{fmt(100 * t.p_optimal_sub, 1)}%</td><td>{t.accepted ? '✔' : '✘'}</td><td>{fmt(t.energy, 0)}</td></tr>
          ))}</tbody>
        </table>
        <h4>Selected: {m.method}</h4>
        <Assignment instance={L} assignment={m.assignment} />
      </div>
    </div>
  )
}

function GroverTab({ data }) {
  const rows = data.grover
  return (
    <div className="single">
      <h3>Dürr–Høyer quantum minimum search inside RAPTOR's label selection</h3>
      <p className="muted">RAPTOR's last step picks the best of N candidate arrival labels. Classically: N−1 comparisons. Dürr–Høyer (Grover + BBHT schedule) needs O(√N) oracle queries. We count <b>oracle queries</b>, not wall-clock time — on a simulator the quantum version is far slower. The oracle is a diagonal phase gate built from the known labels (no QRAM), so this shows query complexity only.</p>
      <table className="tbl">
        <thead><tr><th>N labels</th><th>Qubits</th><th>Classical comparisons</th><th>Quantum queries to min (mean)</th><th>median</th><th>√N</th><th>Success rate</th></tr></thead>
        <tbody>{rows.map((r) => (
          <tr key={r.N}><td>{r.N}</td><td>{r.qubits}</td><td>{r.classical_comparisons}</td><td>{fmt(r.mean_queries_to_min)}</td><td>{fmt(r.median_queries_to_min)}</td><td>{fmt(r.sqrtN)}</td><td>{fmt(100 * r.success_rate, 0)}%</td></tr>
        ))}</tbody>
      </table>
      <div style={{ maxWidth: 640 }}>
        <LineChart width={520} height={220} xLabel="N (number of labels)" yLabel="queries / comparisons" series={[
          { name: 'classical N−1', color: '#dc2626', points: rows.map((r) => [r.N, r.classical_comparisons]) },
          { name: 'Dürr–Høyer (sim)', color: '#2563eb', points: rows.map((r) => [r.N, r.mean_queries_to_min]) },
          { name: '√N', color: '#94a3b8', dash: '4 4', points: rows.map((r) => [r.N, r.sqrtN]) },
        ]} />
      </div>
    </div>
  )
}

export default function Study() {
  const [data, setData] = useState(null)
  const [tab, setTab] = useState('small')
  useEffect(() => { fetch('./results.json').then((r) => r.json()).then(setData) }, [])
  const net = data?.network
  const stats = useMemo(() => net && `${net.stops.length} stops · ${net.num_lines} lines · ${net.num_routes} RAPTOR routes · ${net.num_trips} timetabled trips · ${net.damaged.length} flood-damaged segments`, [net])
  if (!data) return <div className="loading">Loading results.json … (run <code>uv run qroute-demo</code> in /backend first)</div>
  return (
    <div className="study app">
      <header>
        <div>
          <h1>Quantum Evacuation Routing — Karachi storm-surge scenario</h1>
          <div className="muted">{stats}</div>
        </div>
        <nav>
          {[['small', '12-qubit QAOA vs exact'], ['large', 'City-scale (clustered)'], ['grover', 'Grover min-search']].map(([k, l]) => (
            <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{l}</button>
          ))}
        </nav>
      </header>
      <div className="pipeline">
        <span>① Synthetic transit network on real map</span>→<span>② RAPTOR: Pareto journeys per group (classical, exact)</span>→<span>③ QUBO: time + bus crowding + shelter load</span>→<span>④ QAOA on Qiskit Aer (penalty vs XY-mixer)</span>→<span>⑤ Compare to brute-force / greedy / annealing</span>
      </div>
      {tab === 'small' && <SmallTab data={data} network={net} />}
      {tab === 'large' && <LargeTab data={data} network={net} />}
      {tab === 'grover' && <GroverTab data={data} />}
    </div>
  )
}
