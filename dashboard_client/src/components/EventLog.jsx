export default function EventLog({ lastEvent, error }) {
  return <section className="panel event-log"><h2>Event log</h2>{error && <p className="error">{error}</p>}{lastEvent ? <p>{lastEvent.message || lastEvent.description || lastEvent.event_type}</p> : <p>Connected dashboard events appear here.</p>}</section>
}
