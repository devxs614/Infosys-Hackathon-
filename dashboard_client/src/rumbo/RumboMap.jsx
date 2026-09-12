import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useMemo, useRef } from 'react'
import { CircleMarker, MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap, useMapEvents } from 'react-leaflet'
import { monterreyCenter } from './data'

const tileUrl = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
const tileAttribution = '&copy; OpenStreetMap contributors &copy; CARTO'

function icon(kind, bearing = 0) {
  const symbols = { pickup: '●', destination: '⌖', driver: '➤' }
  return L.divIcon({
    className: `rumbo-marker rumbo-marker-${kind}`,
    html: `<span style="transform:rotate(${kind === 'driver' ? bearing : 0}deg)">${symbols[kind] || '●'}</span>`,
    iconSize: [34, 34], iconAnchor: [17, 17],
  })
}

function Bounds({ points }) {
  const map = useMap()
  const fitted = useRef(false)
  useEffect(() => {
    if (!fitted.current && points.length > 1) {
      fitted.current = true
      map.fitBounds(points, { padding: [34, 34], maxZoom: 14, animate: true })
    }
  }, [map, points])
  return null
}

function ClickToPlace({ onChange }) {
  useMapEvents({ click: (event) => onChange?.([event.latlng.lat, event.latlng.lng]) })
  return null
}

function normalizeRoute(route, routeCoordinates) {
  if (!route?.length) return []
  return route.map(([first, second]) => routeCoordinates === 'latlng' ? [first, second] : [second, first])
}

export function RumboMap({
  className = '', origin, destination, route = [], routeCoordinates = 'lonlat', driver, orders = [],
  interactive = false, onDestinationChange, showBounds = true,
}) {
  const originPoint = origin?.coords || origin
  const destinationPoint = destination?.coords || destination
  const line = useMemo(() => normalizeRoute(route, routeCoordinates), [route, routeCoordinates])
  const orderPoints = orders.map((order) => order.destination || order.location).filter(Boolean)
  const points = [originPoint, destinationPoint, driver?.position, ...line, ...orderPoints].filter(Boolean)
  return <div className={`rumbo-map relative overflow-hidden rounded-[1.6rem] border border-white/10 bg-[#0a111c] ${className}`}>
    <MapContainer center={destinationPoint || originPoint || monterreyCenter} zoom={12} scrollWheelZoom className="h-full w-full" zoomControl={false} attributionControl>
      <TileLayer url={tileUrl} attribution={tileAttribution} />
      {showBounds && <Bounds points={points} />}
      {interactive && <ClickToPlace onChange={onDestinationChange} />}
      {line.length > 1 && <><Polyline positions={line} pathOptions={{ color: '#06b6d4', weight: 8, opacity: .18, lineCap: 'round' }} /><Polyline positions={line} pathOptions={{ color: '#8b5cf6', weight: 4, opacity: .96, lineCap: 'round' }} /></>}
      {originPoint && <Marker position={originPoint} icon={icon('pickup')}><Tooltip direction="top" offset={[0, -12]}>{origin?.name || 'Origen · Rumbo Kitchen'}</Tooltip></Marker>}
      {destinationPoint && <Marker position={destinationPoint} icon={icon('destination')} draggable={interactive} eventHandlers={{ dragend: (event) => { const point = event.target.getLatLng(); onDestinationChange?.([point.lat, point.lng]) } }}><Tooltip direction="top" offset={[0, -12]} permanent={interactive}>{destination?.name || 'Entrega'}</Tooltip></Marker>}
      {driver?.position && <Marker position={driver.position} icon={icon('driver', driver.bearing)}><Tooltip direction="top" offset={[0, -12]}>{driver.name || 'Courier Rumbo'} · {driver.street_name || 'En ruta'}</Tooltip></Marker>}
      {orderPoints.map((point, index) => <CircleMarker key={`${point.join('-')}-${index}`} center={point} radius={6} pathOptions={{ color: '#22d3ee', fillColor: '#06b6d4', fillOpacity: .7 }} />)}
    </MapContainer>
    <div className="pointer-events-none absolute bottom-4 left-4 z-[500] rounded-xl border border-white/10 bg-black/55 px-3 py-2 text-[9px] font-semibold tracking-[.16em] text-cyan/90 backdrop-blur">MONTERREY · LIVE STREET GRAPH</div>
  </div>
}
