export const CONVOY = ['#d9480f', '#1971c2', '#2f9e44', '#9c36b5']
export const easeInOut = (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2)
export const clamp01 = (x) => Math.max(0, Math.min(1, x))

export function fmtBig(v) {
  if (v == null) return '–'
  if (v < 10000) return Math.round(v).toLocaleString()
  if (v < 1e6) return `${Math.round(v / 1e3)}k`
  if (v < 1e9) return `${(v / 1e6).toFixed(1)}M`
  if (v < 1e12) return `${(v / 1e9).toFixed(1)}B`
  const e = Math.floor(Math.log10(v))
  return `${(v / 10 ** e).toFixed(1)}e${e}`
}

async function getJson(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(r.statusText)
  return r.json() // throws if the dev server answers with index.html
}

/* Index of cases; falls back to the mock when the real files are not there yet. */
export async function loadIndex() {
  try {
    const idx = await getJson('/cases/index.json')
    if (Array.isArray(idx) && idx.length) return { list: idx, mock: false }
  } catch { /* fall through */ }
  const m = await getJson('/cases/_mock.json')
  return { list: [{ id: m.id, title: m.title, region: m.region, disaster: m.disaster, k: m.k, n: m.n, N: m.N, qubits: m.qubits }], mock: true }
}

export const loadCase = (id) => getJson(`/cases/${id}.json`)

/* Road geometry for one convoy route; straight lines where a leg is missing. */
export function routeCoords(c, route) {
  const out = []
  for (let i = 0; i + 1 < route.length; i++) {
    const a = route[i], b = route[i + 1]
    const leg = c.legs?.[`${a}-${b}`]
    if (leg?.length) out.push(...leg)
    else {
      const rev = c.legs?.[`${b}-${a}`]
      if (rev?.length) out.push(...[...rev].reverse())
      else out.push([c.points[a].lat, c.points[a].lon], [c.points[b].lat, c.points[b].lon])
    }
  }
  return out
}

export function bestUpTo(samples, qi) {
  let best = null
  for (let i = 0; i <= qi && i < samples.length; i++) if (!best || samples[i].cost_s < best.cost_s) best = samples[i]
  return best
}
