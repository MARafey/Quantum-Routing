import L from 'leaflet'

// Canvas layer that draws the first `count` of many points cheaply.
// Used to replay search exploration (tens of thousands of settled road nodes).
export const DotLayer = L.Layer.extend({
  initialize(color) {
    this._color = color
    this._groups = [] // [{ points: [[lat, lon]...], count }]
  },
  onAdd(map) {
    this._map = map
    this._canvas = L.DomUtil.create('canvas', 'dot-layer')
    this._canvas.style.pointerEvents = 'none'
    map.getPanes().overlayPane.appendChild(this._canvas)
    map.on('moveend zoomend resize', this._reset, this)
    this._reset()
  },
  onRemove(map) {
    L.DomUtil.remove(this._canvas)
    map.off('moveend zoomend resize', this._reset, this)
  },
  setGroups(groups) {
    this._groups = groups.map((pts) => ({ points: pts, count: 0 }))
    this._draw()
  },
  setCounts(counts) {
    counts.forEach((c, i) => { if (this._groups[i]) this._groups[i].count = c })
    this._draw()
  },
  _reset() {
    const size = this._map.getSize()
    const tl = this._map.containerPointToLayerPoint([0, 0])
    L.DomUtil.setPosition(this._canvas, tl)
    const dpr = window.devicePixelRatio || 1
    this._canvas.width = size.x * dpr
    this._canvas.height = size.y * dpr
    this._canvas.style.width = size.x + 'px'
    this._canvas.style.height = size.y + 'px'
    this._draw()
  },
  _draw() {
    if (!this._map || !this._canvas) return
    const ctx = this._canvas.getContext('2d')
    const dpr = window.devicePixelRatio || 1
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, this._canvas.width, this._canvas.height)
    ctx.fillStyle = this._color
    const origin = this._map.containerPointToLayerPoint([0, 0])
    for (const g of this._groups) {
      const n = Math.min(g.count, g.points.length)
      for (let i = 0; i < n; i++) {
        const p = this._map.latLngToLayerPoint(g.points[i])
        ctx.fillRect(p.x - origin.x - 1.25, p.y - origin.y - 1.25, 2.5, 2.5)
      }
    }
  },
})
