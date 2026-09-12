import { useEffect, useRef, useState } from 'react'
import { createSimulationSocket } from '../services/websocket'

export function useWebSocket(onMessage) {
  const [status, setStatus] = useState('connecting')
  const socketRef = useRef(null)
  useEffect(() => {
    socketRef.current = createSimulationSocket(onMessage, setStatus)
    return () => socketRef.current?.close()
  }, [onMessage])
  return { status }
}

