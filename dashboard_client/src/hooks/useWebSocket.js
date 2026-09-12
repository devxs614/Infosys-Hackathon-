import { useEffect, useRef, useState } from 'react'
import { createSimulationSocket } from '../services/websocket'

export function useWebSocket(onMessage) {
  const [status, setStatus] = useState('connecting')
  const socketRef = useRef(null)
  useEffect(() => {
    socketRef.current = createSimulationSocket(onMessage, setStatus)
    return () => socketRef.current?.close()
  }, [onMessage])
  const send = (message) => {
    if (socketRef.current?.readyState !== WebSocket.OPEN) return false
    socketRef.current.send(JSON.stringify(message))
    return true
  }
  return { status, send }
}
