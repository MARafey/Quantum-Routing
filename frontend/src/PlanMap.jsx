import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

/* Playback storyboard (ms) */
export const SAMPLES_MS = 3000 // act 1: flash through the quantum samples
export const ROUTE_MS = 1200 // act 2: draw the best plan
export const CONVOY_COLORS = ['#d9480f', '#1971c2', '#2f9e44']
const PAKISTAN = [[23.6, 60.9], [37.1, 77.8]]

const ease = (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2)

function tag(cls, text) {
  return L.divIcon({ className: '', html: `<span class="mtag ${cls}">${text}</span>`, iconSize: [24, 24], iconAnchor: [12, 12] })
}

function partial(pts, f) {
  if (f >= 1) return pts
  const seg = []
  let total = 0
  for (let i = 1; i < pts.length; i++) { const d = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); seg.push(d); total += d }
  let want = total * f
  const out = [pts[0]]
  for (let i = 0; i < seg.length; i++) {
    if (want >= seg[i]) { out.push(pts[i + 1]); want -= seg[i]; continue }
    const t = seg[i] ? want / seg[i] : 0
    out.push([pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t])
    break
  }
  return out
}

export default function PlanMap({ hubs, sites, mode, canAdd, onAdd, playback }) {
  const el = useRef(null)
  const map = useRef(null)
  const markers = useRef(null)
  const routes = useRef(null)
  const live = useRef({})
  live.current = { onAdd, canAdd }

  useEffect(() => {
    const m = L.map(el.current, { zoomControl: true, attributionControl: true, minZoom: 4 }).fitBounds(PAKISTAN)
    const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '© OpenStreetMap contributors', maxZoom: 18 }).addTo(m)
    tiles.getContainer().classList.add('gray-tiles')
    markers.current = L.layerGroup().addTo(m)
    routes.current = L.layerGroup().addTo(m)
    m.on('click', (e) => { if (live.current.canAdd) live.current.onAdd(e.latlng.lat, e.latlng.lng) })
    map.current = m
    return () => { m.remove(); map.current = null }
  }, [])

  useEffect(() => { el.current.dataset.mode = mode }, [mode])

  useEffect(() => {
    markers.current.clearLayers()
    hubs.forEach((p, i) => L.marker([p.lat, p.lon], { icon: tag('hub', String.fromCharCode(65 + i)), title: p.name, interactive: false }).addTo(markers.current))
    sites.forEach((p, i) => L.marker([p.lat, p.lon], { icon: tag('site', i + 1), title: p.name, interactive: false }).addTo(markers.current))
  }, [hubs, sites])

  useEffect(() => {
    routes.current.clearLayers()
    if (!playback) return
    const r = playback.result
    const pts = r.points.map((p) => [p.lat, p.lon])
    const k = r.k
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    map.current.fitBounds(L.latLngBounds(pts), { padding: [60, 60], maxZoom: 9 })
    let raf = 0, cancelled = false

    const drawFinal = () => {
      routes.current.clearLayers()
      r.best.geometry.forEach((g, i) => L.polyline(g, { color: CONVOY_COLORS[i % 3], weight: 5, opacity: 0.95, lineJoin: 'round' }).addTo(routes.current))
    }
    if (reduce) { drawFinal(); return }

    const samples = r.methods.quantum.samples || []
    const lines = r.best.geometry.map((g, i) => L.polyline([], { color: CONVOY_COLORS[i % 3], weight: 5, opacity: 0.95, lineJoin: 'round' }))
    const act2 = (t0) => {
      routes.current.clearLayers()
      lines.forEach((l) => l.addTo(routes.current))
      const tick = (now) => {
        if (cancelled) return
        const f = Math.min(1, (now - t0) / ROUTE_MS)
        lines.forEach((l, i) => l.setLatLngs(partial(r.best.geometry[i], ease(f))))
        if (f < 1) raf = requestAnimationFrame(tick)
      }
      raf = requestAnimationFrame(tick)
    }
    const start = performance.now()
    let shown = -1
    const tick1 = (now) => {
      if (cancelled) return
      const f = (now - start) / SAMPLES_MS
      if (f >= 1 || !samples.length) { act2(now); return }
      const idx = Math.floor(f * samples.length)
      if (idx !== shown) {
        shown = idx
        routes.current.clearLayers()
        samples[idx].routes.forEach((rt, ci) => {
          const path = rt.length && rt[0] < k ? rt : [ci, ...rt]
          L.polyline(path.map((j) => pts[j]), { color: CONVOY_COLORS[ci % 3], weight: 2, opacity: 0.35 }).addTo(routes.current)
        })
      }
      raf = requestAnimationFrame(tick1)
    }
    raf = requestAnimationFrame(tick1)
    return () => { cancelled = true; cancelAnimationFrame(raf) }
  }, [playback])

  return <div className="map" ref={el} />
}
