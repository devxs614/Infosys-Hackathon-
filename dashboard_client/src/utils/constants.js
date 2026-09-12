export const monterreyCenter = [25.6866, -100.3161]
export const eventButtons = [
  ['TORRENTIAL_RAIN', 'Torrential rain'], ['GONZALITOS_FLOOD', 'Gonzalitos flood'],
  ['EXTREME_HEAT', '40°C heat'], ['SAN_PEDRO_SURGE', 'San Pedro surge'], ['ROAD_CLOSURE', 'Road closure']
]

const configuredHost = import.meta.env.VITE_WS_HOST?.trim()
const configuredPort = import.meta.env.VITE_WS_PORT?.trim() || '8765'
// No fixed localhost: browser hostname makes local development work, while a LAN IP is configured by .env.
export const edgeHost = configuredHost || window.location.hostname
export const apiBaseUrl = `${window.location.protocol === 'https:' ? 'https' : 'http'}://${edgeHost}:${configuredPort}`
export const wsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${edgeHost}:${configuredPort}/ws`

