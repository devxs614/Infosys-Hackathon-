export default function DisruptionPanel({ events = [] }) {
  return <section className="panel disruptions"><h2>Active disruptions</h2>{events.length ? <ul>{events.map((event) => <li key={event.id}><b>{event.event_type.replaceAll('_', ' ')}</b><span>{event.zone}</span></li>)}</ul> : <p>No active events.</p>}</section>
}

