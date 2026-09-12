import { useCallback, useEffect, useState } from 'react'

export function useRumboRoute() {
  const [url, setUrl] = useState(() => new URL(window.location.href))
  useEffect(() => {
    const update = () => setUrl(new URL(window.location.href))
    window.addEventListener('popstate', update)
    return () => window.removeEventListener('popstate', update)
  }, [])
  const navigate = useCallback((target) => {
    window.history.pushState({}, '', target)
    window.dispatchEvent(new PopStateEvent('popstate'))
  }, [])
  return { path: url.pathname, query: url.searchParams, navigate }
}
