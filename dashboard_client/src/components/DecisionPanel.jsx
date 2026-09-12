import { money, number } from '../utils/formatters'

export default function DecisionPanel({ decision }) {
  const item = decision || {}
  return <section className="panel decision"><h2>Latest AI decision</h2><div className="decision-type">{item.decision_type || 'WAIT'}</div><p>{item.reasoning || 'Waiting for the first simulation decision.'}</p><dl><dt>Orders</dt><dd>{item.selected_order_ids?.join(', ') || '—'}</dd><dt>Expected earnings</dt><dd>{money(item.estimated_profit_mxn)}</dd><dt>ETA</dt><dd>{number(item.estimated_duration_minutes)} min</dd><dt>Confidence</dt><dd>{number((item.confidence || 0) * 100, 0)}%</dd></dl></section>
}

