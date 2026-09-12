import { CircleMarker, MapContainer, Polyline, Popup, TileLayer } from 'react-leaflet'
import { monterreyCenter } from '../utils/constants'

export default function LiveMap({ state }) {
  const baseline = state?.baseline
  const ai = state?.ai_driver
  const orders = state?.orders || []
  return <section className="panel map-panel"><div className="panel-heading"><h2>Monterrey live map</h2><small>Map tiles are optional; simulation remains local.</small></div>
    <MapContainer center={monterreyCenter} zoom={12} scrollWheelZoom className="map">
      <TileLayer attribution="© OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      {orders.filter((o) => o.status === 'AVAILABLE').map((o) => <CircleMarker key={o.id} center={[o.pickup_lat, o.pickup_lon]} radius={6} pathOptions={{ color: '#f9b949' }}><Popup>{o.id} · {o.restaurant}</Popup></CircleMarker>)}
      {baseline && <CircleMarker center={[baseline.lat, baseline.lon]} radius={9} pathOptions={{ color: '#fc6c85', fillOpacity: 1 }}><Popup>Baseline driver</Popup></CircleMarker>}
      {ai && <CircleMarker center={[ai.lat, ai.lon]} radius={9} pathOptions={{ color: '#3dd9a5', fillOpacity: 1 }}><Popup>AI / Gemini driver</Popup></CircleMarker>}
      {ai?.current_order_ids?.length > 0 && <Polyline positions={[[ai.lat, ai.lon], [orders.find((o) => o.id === ai.current_order_ids[0])?.pickup_lat || ai.lat, orders.find((o) => o.id === ai.current_order_ids[0])?.pickup_lon || ai.lon]]} pathOptions={{ color: '#3dd9a5' }} />}
    </MapContainer>
  </section>
}

