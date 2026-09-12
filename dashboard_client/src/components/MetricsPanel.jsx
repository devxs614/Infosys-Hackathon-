import { money, number } from '../utils/formatters'

function DriverMetrics({ label, metrics, accent }) {
  return <article className="metric-card" style={{ '--accent': accent }}><h3>{label}</h3>
    <strong>{money(metrics?.gross_earnings_mxn)}</strong><span>gross earnings</span>
    <div className="metric-grid"><div><b>{number(metrics?.mxn_per_hour, 0)}</b><small>MXN/hour</small></div><div><b>{number(metrics?.distance_km)}</b><small>km</small></div><div><b>{metrics?.orders_completed || 0}</b><small>orders</small></div><div><b>{metrics?.late_orders || 0}</b><small>late</small></div></div>
  </article>
}

export default function MetricsPanel({ metrics }) {
  return <section className="metrics"><DriverMetrics label="Baseline Driver" metrics={metrics?.baseline} accent="#fc6c85" /><DriverMetrics label="AI / Gemini Driver" metrics={metrics?.ai} accent="#3dd9a5" /></section>
}

