import { wsUrl } from '../utils/constants'

export function createSimulationSocket(onMessage, onStatus) {
  const socket = new WebSocket(wsUrl)
  socket.onopen = () => onStatus('connected')
  socket.onclose = () => onStatus('disconnected')
  socket.onerror = () => onStatus('error')
  socket.onmessage = (event) => {
    try { onMessage(JSON.parse(event.data)) } catch { /* Ignore malformed network frames. */ }
  }
  return socket
}

