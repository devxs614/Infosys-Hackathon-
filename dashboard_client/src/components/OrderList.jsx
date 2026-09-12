import { money, number } from '../utils/formatters'

export default function OrderList({ orders = [] }) {
  return <section className="panel orders"><div className="panel-heading"><h2>Available orders</h2><small>{orders.filter((o) => o.status === 'AVAILABLE').length} open</small></div><div className="order-list">{orders.slice(-10).reverse().map((order) => <div className="order-row" key={order.id}><b>{order.id}</b><span>{order.restaurant} · {order.zone}</span><span>{money(order.courier_payout_mxn)} · {number(order.distance_km)} km</span><em className={order.status.toLowerCase()}>{order.status}</em></div>)}{orders.length === 0 && <p>No orders yet—start the demo.</p>}</div></section>
}

