import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useMemo, useRef, useState } from 'react'
import { CircleMarker, MapContainer, Marker, Polygon, Polyline, TileLayer, Tooltip, useMap, useMapEvents } from 'react-leaflet'
import { monterreyCenter } from './data'

// CARTO Dark Matter is intentionally keyless: every demo laptop can render it.
const tileUrl = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
const tileAttribution = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
export const flaggedZones = [
  { id: 99, name: 'Independencia', center: [25.6814, -100.3218], area: [[25.6778, -100.329], [25.6778, -100.315], [25.685, -100.315], [25.685, -100.329]] },
  { id: 13, name: 'Topo Chico', center: [25.744, -100.351], area: [[25.739, -100.36], [25.739, -100.342], [25.749, -100.342], [25.749, -100.36]] },
  { id: 15, name: 'La Campana', center: [25.639, -100.286], area: [[25.635, -100.294], [25.635, -100.278], [25.643, -100.278], [25.643, -100.294]] },
  { id: 22, name: 'Escobedo North', center: [25.812, -100.322], area: [[25.806, -100.332], [25.806, -100.312], [25.818, -100.312], [25.818, -100.332]] },
  { id: 31, name: 'Guadalupe East', center: [25.604, -100.184], area: [[25.599, -100.194], [25.599, -100.174], [25.609, -100.174], [25.609, -100.194]] },
]

export function flaggedZoneAt(position) {
  if (!position) return null
  const [lat, lon] = position
  return flaggedZones.find((zone) => {
    const lats = zone.area.map(([value]) => value)
    const lons = zone.area.map(([, value]) => value)
    return lat >= Math.min(...lats) && lat <= Math.max(...lats) && lon >= Math.min(...lons) && lon <= Math.max(...lons)
  }) || null
}

function icon(kind, bearing = 0) {
  const symbols = { pickup: '●', destination: '⌖', driver: '➤', flag: '🚩', closure: '🛑' }
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
  const kmBetween = (from, to) => {
    const radius = 6371
    const dLat = (to[0] - from[0]) * Math.PI / 180
    const dLon = (to[1] - from[1]) * Math.PI / 180
    const a = Math.sin(dLat / 2) ** 2 + Math.cos(from[0] * Math.PI / 180) * Math.cos(to[0] * Math.PI / 180) * Math.sin(dLon / 2) ** 2
    return radius * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
  }
  const segmentLengths = line.slice(1).map((point, index) => kmBetween(line[index], point))
  const total = Math.max(segmentLengths.reduce((sum, value) => sum + value, 0), .000001)
  let remaining = progress * total
  for (let index = 0; index < segmentLengths.length; index += 1) {
    const length = segmentLengths[index]
    if (remaining <= length || index === segmentLengths.length - 1) {
      const fraction = Math.min(1, remaining / Math.max(length, .000001))
      const from = line[index]
      const to = line[index + 1]
      const position = [from[0] + (to[0] - from[0]) * fraction, from[1] + (to[1] - from[1]) * fraction]
      return { position, bearing: bearingBetween(position, to), progress, index }
    }
    remaining -= length
  }
  const finalIndex = line.length - 2
  return { position: line.at(-1), bearing: bearingBetween(line[finalIndex], line.at(-1)), progress, index: finalIndex }
}

function splitRoute(line, progress) {
  if (!line.length || typeof progress !== 'number') return { completed: [], pending: line }
  const point = pointAtProgress(line, progress)
  const index = point.index ?? 0
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
  const currentProgress = useRef(lastProgress.current)
  useEffect(() => {
    if (!driver?.position || !line.length || typeof driver.progress !== 'number') {
      setMoving(driver ? { ...driver } : null)
      return undefined
    }
    const target = Math.min(1, Math.max(0, driver.progress))
    const from = target < currentProgress.current ? 0 : currentProgress.current
    let previousFrame = performance.now()
    let elapsed = 0
    let frame = 0
    const animate = (now) => {
      // Delta-time keeps display interpolation stable at any frame rate. The
      // server owns the route physics (exactly 3 seconds per kilometre) and
      // sends a fresh progress snapshot every 500 ms.
      elapsed += now - previousFrame
      previousFrame = now
      // The server owns physical speed (moto 1 km/3 s, car/bike adjusted).
      // This only fills its 500 ms telemetry cadence at display frame rate.
      const ratio = Math.min(1, elapsed / 500)
      const routePoint = pointAtProgress(line, from + (target - from) * ratio)
      currentProgress.current = routePoint.progress
      const next = { ...driver, ...routePoint }
      setMoving(next)
      if (ratio < 1) frame = requestAnimationFrame(animate)
      else lastProgress.current = target
    }
    frame = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(frame)
  }, [driver?.timestamp, driver?.updated_at, driver?.phase, line])
  return moving || driver || null
}

function useProtocolMapState() {
  const [state, setState] = useState({ simulatedMinutes: 0, shock: null, roadClosures: [] })
  useEffect(() => {
    const update = (event) => setState((current) => ({ ...current, ...event.detail }))
    window.addEventListener('rumbo-protocol-visual', update)
    return () => window.removeEventListener('rumbo-protocol-visual', update)
  }, [])
  return state
}

function Bounds({ points, focusKey, focusPoints }) {
  const map = useMap()
  const lastFocus = useRef(null)
  useEffect(() => {
    const nextFocus = focusKey || 'initial'
    const target = focusPoints?.length > 1 ? focusPoints : points
    if (lastFocus.current !== nextFocus && target.length > 1) {
      lastFocus.current = nextFocus
      map.fitBounds(target, { padding: [34, 34], maxZoom: 14, animate: true })
    }
  }, [focusKey, focusPoints, map, points])
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
  className = '', origin, destination, route = [], routeCoordinates = 'lonlat', driver, drivers = [], orders = [],
  courierRoute = [], courierRouteCoordinates = 'lonlat', interactive = false, onDestinationChange, showBounds = true,
  closurePinMode = false, onRoadClosure, focusKey, focusPoints,
}) {
  const originPoint = origin?.coords || origin
  const destinationPoint = destination?.coords || destination
  const line = useMemo(() => normalizeRoute(route, routeCoordinates), [route, routeCoordinates])
  const courierLine = useMemo(() => normalizeRoute(courierRoute, courierRouteCoordinates), [courierRoute, courierRouteCoordinates])
  const protocolState = useProtocolMapState()
  const motionLine = driver?.phase === 'COURIER_TO_STORE' ? courierLine : line
  const movingDriver = usePolylineDriver(driver, motionLine)
  const courierProgress = movingDriver?.phase === 'COURIER_TO_STORE' ? movingDriver.progress : movingDriver?.phase === 'STORE_TO_CLIENT' ? 1 : undefined
  const deliveryProgress = movingDriver?.phase === 'STORE_TO_CLIENT' ? movingDriver.progress : movingDriver?.phase === 'COURIER_TO_STORE' ? 0 : undefined
  const courierSplit = useMemo(() => splitRoute(courierLine, courierProgress), [courierLine, courierProgress])
  const split = useMemo(() => splitRoute(line, deliveryProgress), [line, deliveryProgress])
  const orderPoints = orders.map((order) => order.destination || order.location).filter(Boolean)
  const movingDriverId = movingDriver?.id || movingDriver?.driver_id
  const otherDrivers = drivers.filter((item) => item?.position && item.id !== movingDriverId)
  const closures = protocolState.roadClosures || []
  const points = [originPoint, destinationPoint, movingDriver?.position, ...otherDrivers.map((item) => item.position), ...courierLine, ...line, ...orderPoints, ...closures.map((closure) => closure.position)].filter(Boolean)
  const nightRestriction = protocolState.simulatedMinutes >= 22 * 60
  return <div className={`rumbo-map relative overflow-hidden rounded-[1.6rem] border border-white/10 bg-[#0a111c] ${closurePinMode ? 'rumbo-map-closure-mode' : ''} ${className}`}>
    <MapContainer center={destinationPoint || originPoint || monterreyCenter} zoom={12} scrollWheelZoom className="h-full w-full" zoomControl={false} attributionControl>
      <TileLayer url={tileUrl} attribution={tileAttribution} />
      {showBounds && <Bounds points={points} focusKey={focusKey} focusPoints={focusPoints} />}
      {(interactive || closurePinMode) && <ClickToPlace onChange={closurePinMode ? onRoadClosure : onDestinationChange} />}
      {flaggedZones.map((zone) => <Polygon key={zone.id} positions={zone.area} pathOptions={{ color: '#ff0055', weight: 1.5, fillColor: '#ff0055', fillOpacity: .25, className: nightRestriction ? 'rumbo-risk-zone rumbo-risk-zone-active' : 'rumbo-risk-zone' }}><Tooltip direction="top" permanent={nightRestriction}>🚩 Zone {zone.id} · {zone.name}</Tooltip></Polygon>)}
      {flaggedZones.map((zone) => <Marker key={`flag-${zone.id}`} position={zone.center} icon={icon('flag')}><Tooltip direction="top" offset={[0, -12]} permanent>🚩 Zone {zone.id} · {zone.name}</Tooltip></Marker>)}
      {closures.map((closure, index) => <Marker key={`closure-${index}-${closure.position?.join('-')}`} position={closure.position} icon={icon('closure')}><Tooltip direction="top" offset={[0, -12]} permanent>🛑 ROAD CLOSED · {closure.label || 'Pinned closure'}</Tooltip></Marker>)}
      {courierLine.length > 1 && <>
        {courierSplit.completed.length > 1 && <Polyline positions={courierSplit.completed} pathOptions={{ color: '#94a3b8', weight: 6, opacity: .32, lineCap: 'round' }} />}
        {courierSplit.pending.length > 1 && <><Polyline positions={courierSplit.pending} pathOptions={{ color: '#f59e0b', weight: 10, opacity: .15, lineCap: 'round', dashArray: '4 10' }} /><Polyline positions={courierSplit.pending} pathOptions={{ color: '#fbbf24', weight: 4, opacity: .96, lineCap: 'round', dashArray: '4 10' }} /></>}
      </>}
      {line.length > 1 && <>
        {split.completed.length > 1 && <Polyline positions={split.completed} pathOptions={{ color: '#94a3b8', weight: 6, opacity: .38, lineCap: 'round' }} />}
        {split.pending.length > 1 && <><Polyline positions={split.pending} pathOptions={{ color: '#06b6d4', weight: 10, opacity: .16, lineCap: 'round' }} /><Polyline positions={split.pending} pathOptions={{ color: '#8b5cf6', weight: 4, opacity: .96, lineCap: 'round' }} /></>}
      </>}
      {originPoint && <Marker position={originPoint} icon={icon('pickup')}><Tooltip direction="top" offset={[0, -12]}>{origin?.name || 'Origen · Rumbo Kitchen'}</Tooltip></Marker>}
      {destinationPoint && <Marker position={destinationPoint} icon={icon('destination')} draggable={interactive} eventHandlers={{ dragend: (event) => { const point = event.target.getLatLng(); onDestinationChange?.([point.lat, point.lng]) } }}><Tooltip direction="top" offset={[0, -12]} permanent={interactive}>{destination?.name || 'Entrega'}</Tooltip></Marker>}
      {movingDriver?.position && <Marker position={movingDriver.position} icon={icon('driver', movingDriver.bearing)}><Tooltip direction="top" offset={[0, -12]}>{movingDriver.name}{movingDriver.street_name ? ` · ${movingDriver.street_name}` : ''}</Tooltip></Marker>}
      {otherDrivers.map((item) => <Marker key={item.id} position={item.position} icon={icon('driver', item.bearing)}><Tooltip direction="top" offset={[0, -12]}>{item.name}{item.street_name ? ` · ${item.street_name}` : ''}</Tooltip></Marker>)}
      {orderPoints.map((point, index) => <CircleMarker key={`${point.join('-')}-${index}`} center={point} radius={6} pathOptions={{ color: '#22d3ee', fillColor: '#06b6d4', fillOpacity: .7 }} />)}
    </MapContainer>
    {protocolState.shock === 'rain' && <div className="protocol-rain pointer-events-none absolute inset-0 z-[450]" />}
    {(protocolState.shock === 'closure' || protocolState.shock === 'delay') && <div className="protocol-closure pointer-events-none absolute inset-0 z-[450]" />}
    {closurePinMode && <div className="pointer-events-none absolute left-1/2 top-5 z-[520] -translate-x-1/2 rounded-2xl border border-rose-300/45 bg-[#170a12]/90 px-4 py-2 text-xs font-medium text-rose-100 backdrop-blur">Pin Road Closure: click an avenue on the map</div>}
    <div className="pointer-events-none absolute bottom-4 left-4 z-[500] rounded-xl border border-white/10 bg-black/55 px-3 py-2 text-[9px] font-semibold tracking-[.16em] text-cyan/90 backdrop-blur">{courierLine.length > 1 ? 'ÁMBAR · COURIER → TIENDA  ·  VIOLETA · TIENDA → CLIENTE' : 'MONTERREY · LIVE STREET GRAPH'}</div>
  </div>
}
