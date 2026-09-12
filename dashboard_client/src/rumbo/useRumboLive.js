import { useCallback, useState } from 'react'
import { demoApi } from '../services/api'

export function useRumboLive() {
  const [simulation, setSimulation] = useState(null)
  const [live, setLive] = useState({ users: [], drivers: [], orders: [], batches: [], batch: null, telemetry: {}, metrics: {}, financials: { platform: {}, drivers: [] }, verdict: null, orderMatches: {} })
  const [notification, setNotification] = useState(null)
  const [error, setError] = useState('')
  const onMessage = useCallback((message) => {
    const data = message.data || {}
    if (message.type === 'hello_response') setSimulation(data.state || null)
    if (message.type === 'simulation_state') setSimulation(data)
    if (message.type === 'live_order_state' || message.type === 'LIVE_ORDER_STATE') setLive((current) => ({ ...current, ...data, orderMatches: current.orderMatches || {} }))
    if (message.type === 'NEW_ORDER') setLive((current) => ({ ...current, orders: [...current.orders.filter((order) => order.id !== data.order?.id), data.order] }))
    if (message.type === 'AI_BATCH_SUGGESTION' || message.type === 'AI_BATCH_OPTIMIZATION') setLive((current) => ({ ...current, batch: data, batches: [...(current.batches || []).filter((batch) => batch.id !== data.id), data] }))
    if (message.type === 'DRIVER_NOTIFICATION') { setLive((current) => ({ ...current, batch: data.batch || current.batch })); setNotification(data) }
    if (message.type === 'DRIVER_ACTION') setLive((current) => ({ ...current, orders: data.orders || [], batch: data.batch || null }))
    if (message.type === 'ORDER_MATCHED') setLive((current) => ({
      ...current,
      orders: [...(current.orders || []).filter((order) => order.id !== data.order?.id), data.order],
      drivers: [...(current.drivers || []).filter((driver) => driver.id !== data.driver?.id), data.driver],
      orderMatches: { ...(current.orderMatches || {}), [data.order?.id]: data },
      financials: data.financials ? { ...current.financials, drivers: [...(current.financials?.drivers || []).filter((financial) => financial.driver_id !== data.financials.driver_id), data.financials] } : current.financials,
    }))
    if (message.type === 'DRIVER_FINANCIAL_UPDATE') setLive((current) => ({
      ...current,
      financials: {
        platform: data.platform || current.financials?.platform || {},
        drivers: [...(current.financials?.drivers || []).filter((financial) => financial.driver_id !== data.financials?.driver_id), ...(data.financials ? [data.financials] : [])],
      },
    }))
    if (message.type === 'VERDICT_EVALUATION') setLive((current) => ({ ...current, verdict: data }))
    if (message.type === 'USER_REGISTERED') setLive((current) => ({ ...current, users: [...(current.users || []).filter((user) => user.id !== data.user?.id), data.user], metrics: data.metrics || current.metrics }))
    if (message.type === 'DRIVER_ONLINE') setLive((current) => ({ ...current, drivers: [...(current.drivers || []).filter((driver) => driver.id !== data.driver?.id), data.driver], metrics: data.metrics || current.metrics }))
    if (message.type === 'DRIVER_TELEMETRY') setLive((current) => ({ ...current, telemetry: { ...(current.telemetry || {}), [data.driver_id]: data } }))
    if (message.type === 'LIVE_METRICS') setLive((current) => ({ ...current, metrics: data }))
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
