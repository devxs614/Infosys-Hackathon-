import { number } from '../utils/formatters'

export default function WeatherPanel({ weather = {} }) {
  return <section className="panel compact"><h2>Weather</h2><div className="weather-value">{number(weather.temperature_c, 0)}°C</div><p>Rain: {number((weather.rain_intensity || 0) * 100, 0)}% · Visibility: {number((weather.visibility ?? 1) * 100, 0)}%</p></section>
}

