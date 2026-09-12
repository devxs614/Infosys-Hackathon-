import { eventButtons } from '../utils/constants'

export default function SimulationControls({ running, onStart, onStop, onReset, onTrigger }) {
  return <section className="panel controls"><h2>Judge controls</h2><div className="control-row"><button className="primary" disabled={running} onClick={onStart}>Start demo</button><button disabled={!running} onClick={onStop}>Stop</button><button onClick={onReset}>Reset</button></div><div className="event-buttons">{eventButtons.map(([event, label]) => <button key={event} onClick={() => onTrigger(event)}>{label}</button>)}</div></section>
}

