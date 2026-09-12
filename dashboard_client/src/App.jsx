import ConnectionStatus from './components/ConnectionStatus'
import DecisionPanel from './components/DecisionPanel'
import DisruptionPanel from './components/DisruptionPanel'
import DriverComparison from './components/DriverComparison'
import EventLog from './components/EventLog'
import LiveMap from './components/LiveMap'
import MetricsPanel from './components/MetricsPanel'
import OrderList from './components/OrderList'
import SimulationControls from './components/SimulationControls'
import TrafficPanel from './components/TrafficPanel'
import WeatherPanel from './components/WeatherPanel'
import { useSimulation } from './hooks/useSimulation'
import { useWebSocket } from './hooks/useWebSocket'

export default function App() {
  const simulation = useSimulation()
  const { status } = useWebSocket(simulation.onMessage)
  const { state } = simulation
  return <main className="app-shell"><header><div><p className="eyebrow">INFOSYS HACKMTY 2026 · THE COURIER</p><h1>Courier Edge Decision System</h1><p className="subtitle">Fair, local comparison of a reactive driver and a strategic AI driver.</p></div><ConnectionStatus status={status} /></header>
    <div className="shift-bar"><span>Scenario seed {state?.scenario_seed ?? '42'}</span><span>Simulation minute {Math.round(state?.simulation_minute || 0)} / {state?.shift_minutes || 240}</span><span className={state?.running ? 'running' : ''}>{state?.running ? '● Demo running' : '● Demo idle'}</span></div>
    <MetricsPanel metrics={state?.metrics} />
    <section className="workspace"><LiveMap state={state} /><aside className="side-stack"><DecisionPanel decision={state?.last_decisions?.gemini} /><SimulationControls running={state?.running} onStart={simulation.start} onStop={simulation.stop} onReset={simulation.reset} onTrigger={simulation.trigger} /></aside></section>
    <section className="lower-grid"><DriverComparison comparison={state?.metrics?.comparison} /><WeatherPanel weather={state?.weather} /><TrafficPanel traffic={state?.traffic} /><DisruptionPanel events={state?.events} /></section>
    <section className="lower-grid orders-grid"><OrderList orders={state?.orders} /><EventLog lastEvent={simulation.lastEvent} error={simulation.error} /></section>
  </main>
}
