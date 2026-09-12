import { percent, number } from '../utils/formatters'

export default function DriverComparison({ comparison }) {
  return <section className="panel comparison"><h2>AI vs Baseline</h2><div className="comparison-grid"><div><b>{percent(comparison?.earnings_improvement)}</b><span>Earnings improvement</span></div><div><b>{percent(comparison?.hourly_improvement)}</b><span>Hourly efficiency</span></div><div><b>{percent(comparison?.distance_efficiency_improvement)}</b><span>MXN/km improvement</span></div><div><b>{number(comparison?.late_order_change, 0)}</b><span>Late-order difference</span></div></div><small>Values are calculated from this run—not a claimed fixed advantage.</small></section>
}

