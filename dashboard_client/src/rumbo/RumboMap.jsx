import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useMemo, useRef, useState } from 'react'
import { CircleMarker, MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap, useMapEvents } from 'react-leaflet'
import { monterreyCenter } from './data'

// CARTO Dark Matter is intentionally keyless: every demo laptop can render it.
const tileUrl = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
const tileAttribution = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'

function icon(kind, bearing = 0) {
  const symbols = { pickup: '●', destination: '⌖', driver: '➤' }
  return L.divIcon({
    className: `rumbo-marker rumbo-marker-${kind}`,
    html: `<span style="transform:rotate(${kind === 'driver' ? bearing : 0}deg)">${symbols[kind] || '●'}</span>`,
    iconSize: [34, 34], iconAnchor: [17, 17],
  })
}

function bearingBetween(from, to) {
  const [lat1, lon1] = from.map((value) => value * Math.PI / 180)
  const [lat2, lon2] = to.map((value) => value * Math.PI / 180)
  const deltaLon = lon2 - lon1
  const x = Math.sin(deltaLon) * Math.cos(lat2)
  const y = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(deltaLon)
  return (Math.atan2(x, y) * 180 / Math.PI + 360) % 360
}

function pointAtProgress(line, rawProgress) {
  const progress = Math.min(1, Math.max(0, rawProgress || 0))
  if (line.length === 0) return null
  if (line.length === 1) return { position: line[0], bearing: 0, progress }
  const scaled = progress * (line.length - 1)
  const index = Math.min(line.length - 1, Math.floor(scaled))
  const nextIndex = Math.min(line.length - 1, index + 1)
  const fraction = scaled - index
  const from = line[index]
  const to = line[nextIndex]
  const position = [from[0] + (to[0] - from[0]) * fraction, from[1] + (to[1] - from[1]) * fraction]
  const finalBearing = bearingBetween(line[line.length - 2], line[line.length - 1])
  return { position, bearing: index < line.length - 1 ? bearingBetween(position, to) : finalBearing, progress }
}

function splitRoute(line, progress) {
  if (!line.length || typeof progress !== 'number') return { completed: [], pending: line }
  const point = pointAtProgress(line, progress)
  const scaled = point.progress * (line.length - 1)
  const index = Math.min(line.length - 1, Math.floor(scaled))
  return {
    completed: [...line.slice(0, index + 1), ...(index < line.length - 1 ? [point.position] : [])],
    pending: [point.position, ...line.slice(index + 1)],
  }
}

/**
 * Interpolate each incoming Raspberry snapshot at display rate along the same
 * OSRM polyline. The marker therefore never cuts across streets between ticks.
 */
function usePolylineDriver(driver, line) {
  const [moving, setMoving] = useState(null)
  const lastProgress = useRef(typeof driver?.progress === 'number' ? driver.progress : 0)
  useEffect(() => {
    if (!driver?.position || !line.length || typeof driver.progress !== 'number') {
      setMoving(driver ? { ...driver } : null)
      return undefined
    }
    const target = Math.min(1, Math.max(0, driver.progress))
    const from = target < lastProgress.current ? 0 : lastProgress.current
    const startedAt = performance.now()
    let frame = 0
    const animate = (now) => {
      const ratio = Math.min(1, (now - startedAt) / 470)
      const routePoint = pointAtProgress(line, from + (target - from) * ratio)
      const next = { ...driver, ...routePoint }
      setMoving(next)
      if (ratio < 1) frame = requestAnimationFrame(animate)
      else lastProgress.current = target
    }
    frame = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(frame)
  }, [driver?.timestamp, driver?.progress, driver?.position?.[0], driver?.position?.[1], line])
  return moving || driver || null
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
  courierRoute = [], courierRouteCoordinates = 'lonlat', interactive = false, onDestinationChange, showBounds = true,
}) {
  const originPoint = origin?.coords || origin
  const destinationPoint = destination?.coords || destination
  const line = useMemo(() => normalizeRoute(route, routeCoordinates), [route, routeCoordinates])
  const courierLine = useMemo(() => normalizeRoute(courierRoute, courierRouteCoordinates), [courierRoute, courierRouteCoordinates])
  const movingDriver = usePolylineDriver(driver, line)
  const split = useMemo(() => splitRoute(line, movingDriver?.progress), [line, movingDriver?.progress])
  const orderPoints = orders.map((order) => order.destination || order.location).filter(Boolean)
  const points = [originPoint, destinationPoint, movingDriver?.position, ...courierLine, ...line, ...orderPoints].filter(Boolean)
  return <div className={`rumbo-map relative overflow-hidden rounded-[1.6rem] border border-white/10 bg-[#0a111c] ${className}`}>
    <MapContainer center={destinationPoint || originPoint || monterreyCenter} zoom={12} scrollWheelZoom className="h-full w-full" zoomControl={false} attributionControl>
      <TileLayer url={tileUrl} attribution={tileAttribution} />
      {showBounds && <Bounds points={points} />}
      {interactive && <ClickToPlace onChange={onDestinationChange} />}
      {courierLine.length > 1 && <><Polyline positions={courierLine} pathOptions={{ color: '#f59e0b', weight: 10, opacity: .13, lineCap: 'round', dashArray: '4 10' }} /><Polyline positions={courierLine} pathOptions={{ color: '#fbbf24', weight: 3, opacity: .9, lineCap: 'round', dashArray: '4 10' }} /></>}
      {line.length > 1 && <>
        {split.completed.length > 1 && <Polyline positions={split.completed} pathOptions={{ color: '#94a3b8', weight: 6, opacity: .38, lineCap: 'round' }} />}
        {split.pending.length > 1 && <><Polyline positions={split.pending} pathOptions={{ color: '#06b6d4', weight: 10, opacity: .16, lineCap: 'round' }} /><Polyline positions={split.pending} pathOptions={{ color: '#8b5cf6', weight: 4, opacity: .96, lineCap: 'round' }} /></>}
      </>}
      {originPoint && <Marker position={originPoint} icon={icon('pickup')}><Tooltip direction="top" offset={[0, -12]}>{origin?.name || 'Origen · Rumbo Kitchen'}</Tooltip></Marker>}
      {destinationPoint && <Marker position={destinationPoint} icon={icon('destination')} draggable={interactive} eventHandlers={{ dragend: (event) => { const point = event.target.getLatLng(); onDestinationChange?.([point.lat, point.lng]) } }}><Tooltip direction="top" offset={[0, -12]} permanent={interactive}>{destination?.name || 'Entrega'}</Tooltip></Marker>}
      {movingDriver?.position && <Marker position={movingDriver.position} icon={icon('driver', movingDriver.bearing)}><Tooltip direction="top" offset={[0, -12]}>{movingDriver.name || 'Courier Rumbo'} · {movingDriver.street_name || 'En ruta'}</Tooltip></Marker>}
      {orderPoints.map((point, index) => <CircleMarker key={`${point.join('-')}-${index}`} center={point} radius={6} pathOptions={{ color: '#22d3ee', fillColor: '#06b6d4', fillOpacity: .7 }} />)}
    </MapContainer>
    <div className="pointer-events-none absolute bottom-4 left-4 z-[500] rounded-xl border border-white/10 bg-black/55 px-3 py-2 text-[9px] font-semibold tracking-[.16em] text-cyan/90 backdrop-blur">{courierLine.length > 1 ? 'ÁMBAR · COURIER → TIENDA  ·  VIOLETA · TIENDA → CLIENTE' : 'MONTERREY · LIVE STREET GRAPH'}</div>
  </div>
}
