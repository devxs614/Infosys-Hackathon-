import { useCallback, useState } from 'react'
import { demoApi } from '../services/api'

export function useRumboLive() {
  const [simulation, setSimulation] = useState(null)
  const [live, setLive] = useState({ orders: [], batch: null })
  const [notification, setNotification] = useState(null)
  const [error, setError] = useState('')
  const onMessage = useCallback((message) => {
    const data = message.data || {}
    if (message.type === 'hello_response') setSimulation(data.state || null)
    if (message.type === 'simulation_state') setSimulation(data)
    if (message.type === 'live_order_state') setLive(data)
    if (message.type === 'NEW_ORDER') setLive((current) => ({ ...current, orders: [...current.orders.filter((order) => order.id !== data.order?.id), data.order] }))
    if (message.type === 'AI_BATCH_SUGGESTION') setLive((current) => ({ ...current, batch: data }))
    if (message.type === 'DRIVER_NOTIFICATION') { setLive((current) => ({ ...current, batch: data.batch || current.batch })); setNotification(data) }
    if (message.type === 'DRIVER_ACTION') setLive({ orders: data.orders || [], batch: data.batch || null })
    if (message.type === 'error') setError(data.message || 'Rumbo Edge reportó un error.')
  }, [])
  const trigger = async (event_type) => {
    try { await demoApi.trigger(event_type) } catch (caught) { setError(caught.message) }
  }
  const startDemo = async () => {
    try { const result = await demoApi.start(); setSimulation(result.state) } catch (caught) { setError(caught.message) }
  }
  return { simulation, live, notification, error, onMessage, trigger, startDemo, dismissNotification: () => setNotification(null) }
}
