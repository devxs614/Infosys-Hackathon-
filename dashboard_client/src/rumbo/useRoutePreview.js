import { useEffect, useState } from 'react'
import { apiBaseUrl } from '../utils/constants'

export function useRoutePreview(origin, destination) {
  const [route, setRoute] = useState(null)
  const [loading, setLoading] = useState(false)
  useEffect(() => {
    if (!origin || !destination) return undefined
    const controller = new AbortController()
    const timer = window.setTimeout(async () => {
      setLoading(true)
      try {
        const response = await fetch(`${apiBaseUrl}/route/estimate`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
          body: JSON.stringify({ origin: origin.coords || origin, destination: destination.coords || destination }),
        })
        if (!response.ok) throw new Error('No route')
        setRoute(await response.json())
      } catch (error) {
        if (error.name !== 'AbortError') setRoute(null)
      } finally { setLoading(false) }
    }, 260)
    return () => { controller.abort(); window.clearTimeout(timer) }
  }, [origin, destination])
  return { route, loading }
}
