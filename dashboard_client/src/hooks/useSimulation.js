import { useCallback, useState } from 'react'
import { demoApi } from '../services/api'

export function useSimulation() {
  const [state, setState] = useState(null)
  const [lastEvent, setLastEvent] = useState(null)
  const [error, setError] = useState('')
  const onMessage = useCallback((message) => {
    if (message.type === 'simulation_state') setState(message.data)
    if (message.type === 'hello_response') setState(message.data.state)
    if (message.type === 'event' || message.type === 'error') setLastEvent(message.data)
  }, [])
  const invoke = async (operation) => {
    try { setError(''); const result = await operation(); if (result.state) setState(result.state) } catch (err) { setError(err.message) }
  }
  return { state, lastEvent, error, onMessage, start: () => invoke(demoApi.start), stop: () => invoke(demoApi.stop), reset: () => invoke(demoApi.reset), trigger: (event) => invoke(() => demoApi.trigger(event)) }
}
