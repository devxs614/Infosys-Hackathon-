import { useCallback, useState } from 'react'
import { demoApi } from '../services/api'

export function useRumboLive() {
  const [simulation, setSimulation] = useState(null)
  const [live, setLive] = useState({ users: [], drivers: [], orders: [], batches: [], batch: null, telemetry: {}, metrics: {}, financials: { platform: {}, drivers: [] }, verdict: null, dispatch_log: null, dispatch_history: [], traffic_impact: null, orderMatches: {}, noDriverOrders: {}, noCouriersNotice: null })
  const [notification, setNotification] = useState(null)
  const [driverNotifications, setDriverNotifications] = useState({})
  const [error, setError] = useState('')
  const onMessage = useCallback((message) => {
    const data = message.data || {}
    if (message.type === 'hello_response') setSimulation(data.state || null)
    if (message.type === 'simulation_state') setSimulation(data)
    if (message.type === 'live_order_state' || message.type === 'LIVE_ORDER_STATE') setLive((current) => ({ ...current, ...data, dispatch_history: data.dispatch_history || current.dispatch_history || [], orderMatches: current.orderMatches || {}, noDriverOrders: current.noDriverOrders || {}, noCouriersNotice: current.noCouriersNotice || null }))
    if (message.type === 'NEW_ORDER') setLive((current) => ({ ...current, orders: [...current.orders.filter((order) => order.id !== data.order?.id), data.order] }))
    if (message.type === 'AI_BATCH_SUGGESTION' || message.type === 'AI_BATCH_OPTIMIZATION') setLive((current) => ({ ...current, batch: data, batches: [...(current.batches || []).filter((batch) => batch.id !== data.id), data] }))
    if (message.type === 'DRIVER_NOTIFICATION') {
      setLive((current) => ({ ...current, batch: data.batch || current.batch }))
      if (data.driver_id) setDriverNotifications((current) => ({ ...current, [data.driver_id]: data }))
      else setNotification(data)
    }
    if (message.type === 'DRIVER_ACTION') setLive((current) => ({ ...current, orders: data.orders || [], batch: data.batch || null }))
    if (message.type === 'ORDER_MATCHED') setLive((current) => ({
      ...current,
      orders: [...(current.orders || []).filter((order) => order.id !== data.order?.id), data.order],
      drivers: [...(current.drivers || []).filter((driver) => driver.id !== data.driver?.id), data.driver],
      orderMatches: { ...(current.orderMatches || {}), [data.order?.id]: data },
      noDriverOrders: Object.fromEntries(Object.entries(current.noDriverOrders || {}).filter(([orderId]) => orderId !== data.order?.id)),
      noCouriersNotice: null,
      financials: data.financials ? { ...current.financials, drivers: [...(current.financials?.drivers || []).filter((financial) => financial.driver_id !== data.financials.driver_id), data.financials] } : current.financials,
    }))
    if (message.type === 'ORDER_DISPATCHED') {
      setLive((current) => ({ ...current, orders: [...(current.orders || []).filter((order) => order.id !== data.order?.id), data.order], noDriverOrders: Object.fromEntries(Object.entries(current.noDriverOrders || {}).filter(([orderId]) => orderId !== data.order?.id)), noCouriersNotice: null }))
      setDriverNotifications((current) => ({ ...current, [data.driver?.id]: { ...data, title: 'New order dispatched', message: `${data.order?.restaurant || ''} → ${data.order?.destination_label || ''}` } }))
    }
    if (message.type === 'NO_DRIVERS_AVAILABLE') setLive((current) => ({
      ...current,
      noDriverOrders: data.order?.id ? { ...(current.noDriverOrders || {}), [data.order.id]: data } : current.noDriverOrders,
      noCouriersNotice: data,
    }))
    if (message.type === 'AI_DISPATCH_LOG') setLive((current) => ({ ...current, dispatch_log: data, dispatch_history: [data, ...(current.dispatch_history || []).filter((item) => item.id !== data.id)].slice(0, 80) }))
    if (message.type === 'DRIVER_FINANCIAL_UPDATE') setLive((current) => ({
      ...current,
      financials: {
        platform: data.platform || current.financials?.platform || {},
        drivers: [...(current.financials?.drivers || []).filter((financial) => financial.driver_id !== data.financials?.driver_id), ...(data.financials ? [data.financials] : [])],
      },
    }))
    if (message.type === 'VERDICT_EVALUATION') setLive((current) => ({ ...current, verdict: data }))
    if (message.type === 'ORDER_CANCELLED') setLive((current) => ({
      ...current,
      orders: [...(current.orders || []).filter((order) => order.id !== data.order?.id), data.order],
      batches: data.batch ? [...(current.batches || []).filter((batch) => batch.id !== data.batch.id), data.batch] : current.batches,
    }))
    if (message.type === 'USER_REGISTERED') setLive((current) => ({ ...current, users: [...(current.users || []).filter((user) => user.id !== data.user?.id), data.user], metrics: data.metrics || current.metrics }))
    if (message.type === 'DRIVER_ONLINE') setLive((current) => ({ ...current, drivers: [...(current.drivers || []).filter((driver) => driver.id !== data.driver?.id), data.driver], metrics: data.metrics || current.metrics }))
    if (message.type === 'DRIVER_OFFLINE') setLive((current) => ({ ...current, drivers: (current.drivers || []).filter((driver) => driver.id !== data.driver?.id), metrics: data.metrics || current.metrics }))
    if (message.type === 'DRIVER_DELAYED') setLive((current) => ({ ...current, drivers: [...(current.drivers || []).filter((driver) => driver.id !== data.driver?.id), ...(data.driver ? [data.driver] : [])] }))
    if (message.type === 'ORDER_REASSIGNED') setLive((current) => ({ ...current, orders: [...(current.orders || []).filter((order) => order.id !== data.order?.id), data.order] }))
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
  return {
    simulation, live, notification, driverNotifications, error, onMessage, trigger, startDemo,
    dismissNoCouriersNotice: () => setLive((current) => ({ ...current, noCouriersNotice: null })),
    dismissNotification: (driverId) => {
      if (driverId) setDriverNotifications((current) => {
        const { [driverId]: _dismissed, ...remaining } = current
        return remaining
      })
      else setNotification(null)
    },
  }
}
