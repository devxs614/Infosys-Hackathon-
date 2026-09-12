import { number } from '../utils/formatters'

export default function TrafficPanel({ traffic = {} }) {
  return <section className="panel compact"><h2>Traffic</h2><div className="weather-value">×{number(traffic.global_factor || 1)}</div><p>{traffic.congestion_level || 'normal'} congestion · {traffic.road_closures?.length || 0} closures</p></section>
}

