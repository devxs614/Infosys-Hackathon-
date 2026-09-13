import { apiBaseUrl } from '../utils/constants'

async function request(path, options = {}) {
  const response = await fetch(`${apiBaseUrl}${path}`, { headers: { 'Content-Type': 'application/json' }, ...options })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || `Edge server returned ${response.status}`)
  }
  return response.json()
}

export const authApi = {
  register: (data) => request('/api/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  login: (data) => request('/api/auth/login', { method: 'POST', body: JSON.stringify(data) }),
}

export const demoApi = {
  start: () => request('/demo/start', { method: 'POST' }), stop: () => request('/demo/stop', { method: 'POST' }),
  reset: () => request('/demo/reset', { method: 'POST' }), state: () => request('/demo/state'),
  trigger: (event_type) => request('/demo/trigger', { method: 'POST', body: JSON.stringify({ event_type }) })
}
