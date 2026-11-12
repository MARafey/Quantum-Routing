import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

export const ROUTE_MS = 1200 // draw the best plan
export const FLICKER_MS = 120 // one candidate plan per tick while searching
export const CONVOY_COLORS = ['#d9480f', '#1971c2', '#2f9e44']

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

const shuffle = (a) => { const b = [...a]; for (let i = b.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [b[i], b[j]] = [b[j], b[i]] } return b }

/* one random valid plan: random site order, random split among hubs */
function randomPlan(hubs, sites) {
  const groups = hubs.map((h) => [[h.lat, h.lon]])
  shuffle(sites).forEach((s) => groups[Math.floor(Math.random() * hubs.length)].push([s.lat, s.lon]))
  return groups
}

export default function PlanMap({ hubs, sites, mode, canAdd, onAdd, playback, searching, bbox, regionKey }) {
  const el = useRef(null)
  const map = useRef(null)
  const markers = useRef(null)
  const routes = useRef(null)
  const bounds = useRef(null)
  const live = useRef({})
  live.current = { onAdd, canAdd, hubs, sites }

  useEffect(() => {
    const m = L.map(el.current, { zoomControl: true, attributionControl: true, minZoom: 3 }).setView([30, 70], 5)
    const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '© OpenStreetMap contributors', maxZoom: 18 }).addTo(m)
    tiles.getContainer().classList.add('gray-tiles')
    bounds.current = L.rectangle([[0, 0], [0, 0]], { color: '#1c1c1a', weight: 1, opacity: 0.5, dashArray: '4 4', fill: false, interactive: false }).addTo(m)
    markers.current = L.layerGroup().addTo(m)
    routes.current = L.layerGroup().addTo(m)
    m.on('click', (e) => { if (live.current.canAdd) live.current.onAdd(e.latlng.lat, e.latlng.lng) })
    map.current = m
    return () => { m.remove(); map.current = null }
  }, [])

  useEffect(() => {
    bounds.current.setBounds(bbox)
    map.current.fitBounds(bbox)
  }, [regionKey]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { el.current.dataset.mode = mode }, [mode])

  useEffect(() => {
    routes.current.clearLayers()
    markers.current.clearLayers()
    hubs.forEach((p, i) => L.marker([p.lat, p.lon], { icon: tag('hub', String.fromCharCode(65 + i)), title: p.name, interactive: false }).addTo(markers.current))
    sites.forEach((p, i) => L.marker([p.lat, p.lon], { icon: tag('site', i + 1), title: p.name, interactive: false }).addTo(markers.current))
  }, [hubs, sites])

  /* while the request is pending: flicker random candidate plans, one at a time */
  useEffect(() => {
    if (!searching) return
    routes.current.clearLayers()
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const { hubs: h, sites: s } = live.current
    if (!h.length || !s.length) return
    const id = setInterval(() => {
      routes.current.clearLayers()
      randomPlan(h, s).forEach((g, ci) => { if (g.length > 1) L.polyline(g, { color: CONVOY_COLORS[ci % 3], weight: 2, opacity: 0.35, interactive: false }).addTo(routes.current) })
    }, FLICKER_MS)
    return () => { clearInterval(id); routes.current.clearLayers() }
  }, [searching])

  /* result: draw the best routes progressively */
  useEffect(() => {
    if (!playback) return
    routes.current.clearLayers()
    const r = playback.result
    const pts = r.points.map((p) => [p.lat, p.lon])
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    map.current.fitBounds(L.latLngBounds(pts), { padding: [60, 60], maxZoom: 9 })
    const opts = (i) => ({ color: CONVOY_COLORS[i % 3], weight: 5, opacity: 0.95, lineJoin: 'round' })
    if (reduce) { r.best.geometry.forEach((g, i) => L.polyline(g, opts(i)).addTo(routes.current)); return }
    const lines = r.best.geometry.map((g, i) => L.polyline([], opts(i)).addTo(routes.current))
    let raf = 0, cancelled = false
    const t0 = performance.now()
    const tick = (now) => {
      if (cancelled) return
      const f = Math.min(1, (now - t0) / ROUTE_MS)
      lines.forEach((l, i) => l.setLatLngs(partial(r.best.geometry[i], ease(f))))
      if (f < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => { cancelled = true; cancelAnimationFrame(raf) }
  }, [playback])

  return <div className="map" ref={el} />
}
