import { MapContainer, TileLayer, Polyline, CircleMarker, Tooltip } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

export const GROUP_COLORS = [
  '#2563eb', '#d97706', '#059669', '#db2777', '#7c3aed', '#0891b2',
  '#65a30d', '#dc2626', '#4f46e5', '#ca8a04', '#0d9488', '#9333ea',
]

export default function MapView({ network, instance, assignment, showAllOptions }) {
  const shelterLoad = {}
  if (assignment) {
    assignment.forEach((r, g) => {
      const opt = instance.options[g][r]
      shelterLoad[opt.shelter] = (shelterLoad[opt.shelter] || 0) + instance.groups[g].size
    })
  }
  const stopByName = Object.fromEntries(network.stops.map((s) => [s.name, s]))

  return (
    <MapContainer center={[24.875, 67.08]} zoom={12} className="map" scrollWheelZoom>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>'
        url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
      />
      {network.lines.map((l) => (
        <Polyline key={l.name} positions={l.path} pathOptions={{ color: '#94a3b8', weight: 3, opacity: 0.7 }}>
          <Tooltip sticky>{l.name} · {l.trips} trips/direction</Tooltip>
        </Polyline>
      ))}
      {network.damaged.map((p, i) => (
        <Polyline key={'d' + i} positions={p} pathOptions={{ color: '#dc2626', weight: 5, dashArray: '6 8' }}>
          <Tooltip sticky>Flood-damaged segment (closed)</Tooltip>
        </Polyline>
      ))}
      {network.stops.filter((s) => !s.landmark).map((s) => (
        <CircleMarker key={s.id} center={[s.lat, s.lon]} radius={2} pathOptions={{ color: '#64748b', weight: 1 }} />
      ))}

      {showAllOptions && instance.options.map((opts, g) =>
        opts.map((o, r) => o.legs.map((leg, li) => (
          <Polyline key={`o${g}-${r}-${li}`} positions={leg.path}
            pathOptions={{ color: GROUP_COLORS[g % 12], weight: 2, opacity: 0.35, dashArray: '2 6' }} />
        ))),
      )}

      {assignment && assignment.map((r, g) => {
        const opt = instance.options[g][r]
        return opt.legs.map((leg, li) => (
          <Polyline key={`a${g}-${li}`} positions={leg.path}
            pathOptions={{ color: GROUP_COLORS[g % 12], weight: leg.kind === 'walk' ? 3 : 6, opacity: 0.85,
              dashArray: leg.kind === 'walk' ? '4 6' : null, offset: g }}>
            <Tooltip sticky>
              Group {g + 1} ({instance.groups[g].origin}, {instance.groups[g].size} people)<br />
              {leg.kind === 'bus' ? `${leg.line}: ${leg.from} → ${leg.to}` : `Walk ${leg.from} → ${leg.to}`}<br />
              t = {leg.dep} → {leg.arr} min
            </Tooltip>
          </Polyline>
        ))
      })}

      {network.shelters.map((s) => {
        const st = stopByName[s.name]
        const load = shelterLoad[s.name] || 0
        const over = load > s.capacity
        return (
          <CircleMarker key={s.name} center={[st.lat, st.lon]} radius={11}
            pathOptions={{ color: over ? '#dc2626' : '#15803d', fillColor: over ? '#fecaca' : '#bbf7d0', fillOpacity: 0.9, weight: 3 }}>
            <Tooltip permanent direction="right" offset={[10, 0]} className="lbl">
              🏥 {s.name} {load}/{s.capacity}
            </Tooltip>
          </CircleMarker>
        )
      })}
      {instance.groups.map((g, i) => (
        <CircleMarker key={'g' + i} center={[g.lat + (g.dep ? 0.004 : 0), g.lon]} radius={6 + g.size / 15}
          pathOptions={{ color: '#1e293b', fillColor: GROUP_COLORS[i % 12], fillOpacity: 0.9, weight: 2 }}>
          <Tooltip>Group {i + 1}: {g.size} evacuees at {g.origin}, ready t={g.dep} min</Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  )
}
