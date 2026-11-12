import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { DotLayer } from './DotLayer.js'
import { ROUTE, fmtMs, stopLetter } from './theme.js'

const easeInOut = (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2)

function tourCoords(legs, perm, ret) {
  const seq = [0, ...perm, ...(ret ? [0] : [])]
  const out = []
  for (let i = 0; i + 1 < seq.length; i++) out.push(...(legs[`${seq[i]}-${seq[i + 1]}`] || []))
  return out
}

function partial(coords, frac) {
  const n = Math.max(2, Math.ceil(coords.length * frac))
  return coords.slice(0, n)
}

const RaceMap = forwardRef(function RaceMap({ method, onMapClick, onMove, attribution }, ref) {
  const el = useRef(null)
  const m = useRef({})
  const cb = useRef({})
  cb.current = { onMapClick, onMove }
  const ui = { clock: useRef(null), count: useRef(null), state: useRef(null), card: useRef(null) }

  useEffect(() => {
    const map = L.map(el.current, { zoomControl: false, attributionControl: attribution, zoomSnap: 0.25 })
      .setView([24.885, 67.08], 11.75)
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 18,
    }).addTo(map)
    const dots = new DotLayer(method.dot).addTo(map)
    const candidate = L.polyline([], { color: method.color, weight: 2, opacity: 0.35 }).addTo(map)
    const best = L.polyline([], { color: method.color, weight: 3.5, opacity: 0.9 }).addTo(map)
    const route = L.polyline([], { color: ROUTE, weight: 5, opacity: 0.95, lineCap: 'round' }).addTo(map)
    const markers = L.layerGroup().addTo(map)
    map.on('click', (e) => cb.current.onMapClick?.(e.latlng))
    map.on('move', () => cb.current.onMove?.(method.key, map.getCenter(), map.getZoom()))
    m.current = { map, dots, candidate, best, route, markers }
    return () => map.remove()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useImperativeHandle(ref, () => ({
    syncTo(center, zoom) { m.current.map.setView(center, zoom, { animate: false }) },
    fit(stops) {
      if (stops.length) m.current.map.fitBounds(L.latLngBounds(stops.map((s) => [s.lat, s.lon])).pad(0.18), { animate: false })
    },
    setStops(stops) {
      const g = m.current.markers
      g.clearLayers()
      stops.forEach((s, i) => {
        const icon = L.divIcon({ className: '', html: `<div class="tag${i === 0 ? ' depot' : ''}">${stopLetter(i)}</div>`, iconSize: [22, 22], iconAnchor: [11, 11] })
        L.marker([s.lat, s.lon], { icon, interactive: false, keyboard: false }).addTo(g)
      })
    },
    clear() {
      const { dots, candidate, best, route } = m.current
      dots.setGroups([])
      candidate.setLatLngs([]); best.setLatLngs([]); route.setLatLngs([])
      ui.clock.current.textContent = '0.00 s'
      ui.count.current.textContent = ''
      ui.state.current.textContent = 'Waiting'
      ui.card.current.dataset.state = 'idle'
    },
    load(result, data) {
      m.current.res = result
      m.current.data = data
      m.current.tours = {
        brute: result.order.tried?.map((t) => ({ ...t, coords: null })),
        samples: result.order.samples,
      }
      m.current.dots.setGroups(result.searches.map((s) => s.sample))
      this.clear()
      m.current.dots.setGroups(result.searches.map((s) => s.sample))
    },
    // t: playback ms; T: timeline description shared by all maps
    frame(t, T) {
      const { res, data, dots, candidate, best, route } = m.current
      if (!res) return
      const s = T.scale
      const searchDur = res.search_ms * s
      const total = res.total_ms * s
      const card = ui.card.current
      // ---- Act 1: the race, proportional to measured wall-clock time
      if (t <= T.act1) {
        const tau = Math.min(t, searchDur)
        const searches = res.searches
        let counts
        if (method.key === 'brute') {
          const sum = searches.reduce((a, x) => a + x.ms, 0)
          let acc = 0
          counts = searches.map((x) => {
            const start = (acc / sum) * searchDur, dur = (x.ms / sum) * searchDur
            acc += x.ms
            return Math.floor(x.sample.length * Math.max(0, Math.min(1, (tau - start) / dur)))
          })
        } else {
          const maxMs = Math.max(...searches.map((x) => x.ms))
          counts = searches.map((x) => Math.floor(x.sample.length * Math.min(1, tau / (searchDur * (x.ms / maxMs)))))
        }
        dots.setCounts(counts)
        const frac = counts.reduce((a, c) => a + c, 0) / Math.max(1, searches.reduce((a, x) => a + x.sample.length, 0))
        const real = Math.min(t, total) / s
        ui.clock.current.textContent = fmtMs(real)
        ui.count.current.textContent = `${Math.round(frac * res.settled).toLocaleString()} road nodes searched`
        if (t < searchDur) { card.dataset.state = 'running'; ui.state.current.textContent = 'Searching roads' }
        else if (t < total) { card.dataset.state = 'running'; ui.state.current.textContent = method.orderVerb }
        else { card.dataset.state = 'done'; ui.state.current.textContent = `Finished · ${T.rank[method.key]}` }
        return
      }
      dots.setCounts(res.searches.map((x) => x.sample.length))
      ui.clock.current.textContent = fmtMs(res.total_ms)
      card.dataset.state = 'done'
      // ---- Act 2: how each one chose the visit order (equal length, for inspection)
      const t2 = t - T.act1
      const o = res.order
      if (t2 <= T.act2) {
        const f = t2 / T.act2
        ui.state.current.textContent = 'Choosing the visit order'
        if (method.key === 'brute' && o.tried) {
          const k = Math.min(o.tried.length - 1, Math.floor(f * o.tried.length))
          let bi = 0
          for (let i = 0; i <= k; i++) if (o.tried[i].cost < o.tried[bi].cost) bi = i
          candidate.setLatLngs(tourCoords(data.legs, o.tried[k].perm, data.return_to_start))
          best.setLatLngs(tourCoords(data.legs, o.tried[bi].perm, data.return_to_start))
          ui.count.current.textContent = `${(k + 1).toLocaleString()} of ${o.tried.length.toLocaleString()} orders checked`
        } else if (method.key === 'quantum' && o.samples?.length) {
          const qNow = f * o.queries
          const seen = o.samples.filter((x) => x.q <= qNow)
          const cur = seen[seen.length - 1] || o.samples[0]
          const bestS = [...seen].reverse().find((x) => x.improved) || o.samples[0]
          candidate.setLatLngs(tourCoords(data.legs, cur.perm, data.return_to_start))
          best.setLatLngs(tourCoords(data.legs, bestS.perm, data.return_to_start))
          ui.count.current.textContent = `${Math.round(qNow)} oracle queries · ${seen.length} measurements`
        } else if (method.key === 'quantum') {
          candidate.setLatLngs([])
          best.setLatLngs(tourCoords(data.legs, o.perm, data.return_to_start))
          ui.count.current.textContent = 'One stop to visit: no order to search'
        } else {
          const k = Math.round(f * o.evaluated)
          candidate.setLatLngs([])
          if (f > 0.98) best.setLatLngs(tourCoords(data.legs, o.perm, data.return_to_start))
          ui.count.current.textContent = `${k.toLocaleString()} of ${o.evaluated.toLocaleString()} DP states`
        }
        return
      }
      // ---- Act 3: the chosen route draws itself
      candidate.setLatLngs([])
      best.setLatLngs([])
      const f3 = Math.min(1, (t2 - T.act2) / T.act3)
      route.setLatLngs(partial(tourCoords(data.legs, o.perm, data.return_to_start), easeInOut(f3)))
      ui.state.current.textContent = res.optimal ? 'Optimal route' : 'Sub-optimal route'
      ui.count.current.textContent = method.key === 'brute' ? `${o.evaluated} orders checked`
        : method.key === 'parallel' ? `${o.evaluated} DP states`
        : o.N > 1 ? `optimum held after ${o.queries_to_min ?? '–'} of ${o.queries} queries` : 'single order, no search needed'
    },
  }))

  return (
    <section className="race" ref={ui.card} data-state="idle" style={{ '--m': method.color }}>
      <header className="race-head">
        <div className="race-title">
          <span className="race-name">{method.name}</span>
          <span className="race-state" ref={ui.state}>Waiting</span>
        </div>
        <div className="race-clock" ref={ui.clock}>0.00 s</div>
      </header>
      <p className="race-how">{method.how}</p>
      <div className="race-map" ref={el} />
      <div className="race-count" ref={ui.count} />
    </section>
  )
})

export default RaceMap
