// Small dependency-free SVG charts.

export function Bars({ rows, max = 1, fmt = (v) => v.toFixed(3), height = 18 }) {
  return (
    <div className="bars">
      {rows.map((r) => (
        <div className="bar-row" key={r.label}>
          <span className="bar-label">{r.label}</span>
          <div className="bar-track" style={{ height }}>
            <div className="bar-fill" style={{ width: `${Math.min(100, (100 * r.value) / max)}%`, background: r.color }} />
          </div>
          <span className="bar-val">{fmt(r.value)}</span>
        </div>
      ))}
    </div>
  )
}

export function LineChart({ series, width = 360, height = 150, xLabel, yLabel }) {
  const all = series.flatMap((s) => s.points)
  if (!all.length) return null
  const xs = all.map((p) => p[0]), ys = all.map((p) => p[1])
  const [x0, x1] = [Math.min(...xs), Math.max(...xs)]
  const [y0, y1] = [Math.min(...ys), Math.max(...ys)]
  const pad = 30
  const sx = (x) => pad + ((x - x0) / (x1 - x0 || 1)) * (width - pad - 8)
  const sy = (y) => height - pad + 8 - ((y - y0) / (y1 - y0 || 1)) * (height - pad - 4)
  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} className="chart">
      <line x1={pad} y1={height - pad + 8} x2={width - 4} y2={height - pad + 8} stroke="#cbd5e1" />
      <line x1={pad} y1={4} x2={pad} y2={height - pad + 8} stroke="#cbd5e1" />
      {series.map((s) => (
        <polyline key={s.name} fill="none" stroke={s.color} strokeWidth="2" strokeDasharray={s.dash || ''}
          points={s.points.map((p) => `${sx(p[0])},${sy(p[1])}`).join(' ')} />
      ))}
      <text x={width / 2} y={height - 2} textAnchor="middle" className="axis">{xLabel}</text>
      <text x={8} y={height / 2} textAnchor="middle" className="axis" transform={`rotate(-90 8 ${height / 2})`}>{yLabel}</text>
      {series.map((s, i) => (
        <g key={'l' + s.name} transform={`translate(${width - 150}, ${12 + i * 14})`}>
          <line x1="0" y1="-3" x2="14" y2="-3" stroke={s.color} strokeWidth="2" strokeDasharray={s.dash || ''} />
          <text x="18" y="0" className="axis">{s.name}</text>
        </g>
      ))}
    </svg>
  )
}

export function Histogram({ values, marks = [], width = 360, height = 120, bins = 24 }) {
  const lo = Math.min(...values), hi = Math.max(...values)
  const counts = new Array(bins).fill(0)
  values.forEach((v) => { counts[Math.min(bins - 1, Math.floor(((v - lo) / (hi - lo || 1)) * bins))]++ })
  const cmax = Math.max(...counts)
  const bw = (width - 20) / bins
  const sx = (v) => 10 + ((v - lo) / (hi - lo || 1)) * (width - 20)
  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height + 14}`} className="chart">
      {counts.map((c, i) => (
        <rect key={i} x={10 + i * bw} y={height - (c / cmax) * (height - 10)} width={bw - 1}
          height={(c / cmax) * (height - 10)} fill="#cbd5e1" />
      ))}
      {marks.map((m) => (
        <g key={m.label}>
          <line x1={sx(m.value)} x2={sx(m.value)} y1={0} y2={height} stroke={m.color} strokeWidth="2" />
          <text x={sx(m.value) + 3} y={10 + m.row * 11} className="axis" fill={m.color}>{m.label}</text>
        </g>
      ))}
      <text x={10} y={height + 12} className="axis">{lo.toFixed(0)}</text>
      <text x={width - 10} y={height + 12} className="axis" textAnchor="end">{hi.toFixed(0)}</text>
    </svg>
  )
}
