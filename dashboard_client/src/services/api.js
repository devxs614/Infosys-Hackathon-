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
  trigger: (event_type) => request('/demo/trigger', { method: 'POST', body: JSON.stringify({ event_type }) }),
  configure: (data) => request('/protocol/shift-config', { method: 'POST', body: JSON.stringify(data) }),
  setDegraded: (enabled) => request('/protocol/degraded', { method: 'POST', body: JSON.stringify({ enabled }) }),
  timeSync: () => request('/protocol/time-sync'),
  updateTimeSync: (data) => request('/protocol/time-sync', { method: 'POST', body: JSON.stringify(data) }),
  shock: (data) => request('/protocol/shock', { method: 'POST', body: JSON.stringify(data) }),
  pinRoadClosure: (data) => request('/protocol/road-closure', { method: 'POST', body: JSON.stringify(data) }),
  delayDriver: (data) => request('/protocol/driver-delay', { method: 'POST', body: JSON.stringify(data) }),
  launchFullAutonomousDemo: () => request('/protocol/full-autonomous-demo', { method: 'POST' }),
}

export const decisionApi = {
  explain: (orderId) => request(`/explain_decision/${encodeURIComponent(orderId)}`),
}
