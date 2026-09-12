import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { ClientExperience } from './rumbo/ClientExperience'
import { ClientAssignmentModal } from './rumbo/ClientAssignmentModal'
import { CommandCenter } from './rumbo/CommandCenter'
import { DriverHUD } from './rumbo/DriverHUD'
import { Landing } from './rumbo/Landing'
import { useRumboLive } from './rumbo/useRumboLive'
import { useRumboRoute } from './rumbo/useRumboRoute'

const sessionKey = 'rumbo.active-session'

function readSession() {
  try { return JSON.parse(window.localStorage.getItem(sessionKey) || 'null') } catch { return null }
}

function RouteScene({ path, query, navigate, liveState, socket, profile, onAuthenticated, onLogout }) {
  const onHome = () => navigate('/')
  const connected = socket.status === 'connected'
  if (path === '/app/client' && profile?.role === 'client') {
    const clientOrder = (liveState.live.orders || []).find((order) => order.client_id === profile.id && order.status !== 'DELIVERED') || (liveState.live.orders || []).filter((order) => order.client_id === profile.id).at(-1)
    const assignment = clientOrder ? liveState.live.orderMatches?.[clientOrder.id] : null
    return <><ClientExperience profile={profile} live={liveState.live} connected={connected} send={socket.send} onHome={onHome} onLogout={onLogout} /><ClientAssignmentModal assignment={assignment} /></>
  }
  if (path === '/app/driver' && profile?.role === 'driver') return <DriverHUD profile={profile} live={liveState.live} notification={liveState.notification} onDismiss={liveState.dismissNotification} connected={connected} send={socket.send} onHome={onHome} onLogout={onLogout} />
  if (path === '/app/dashboard') return <CommandCenter profile={profile} live={liveState.live} simulation={liveState.simulation} connected={connected} onTrigger={liveState.trigger} onStart={liveState.startDemo} onHome={onHome} onLogout={onLogout} />
  return <Landing onAuthenticated={onAuthenticated} />
}

export default function App() {
  const route = useRumboRoute()
  const liveState = useRumboLive()
  const socket = useWebSocket(liveState.onMessage)
  const [profile, setProfile] = useState(readSession)
  useEffect(() => {
    if (socket.status === 'connected' && profile) socket.send({ type: 'REGISTER_USER', data: profile })
  }, [socket.status, profile])
  const authenticate = (nextProfile) => {
    window.localStorage.setItem(sessionKey, JSON.stringify(nextProfile))
    setProfile(nextProfile)
    route.navigate(nextProfile.role === 'driver' ? '/app/driver' : nextProfile.role === 'admin' ? '/app/dashboard' : '/app/client')
  }
  const logout = () => {
    window.localStorage.removeItem(sessionKey)
    setProfile(null)
    route.navigate('/')
  }
  const routeKey = `${route.path}:${route.query.get('id') || ''}`
  return <AnimatePresence mode="wait"><motion.div key={routeKey} initial={{ opacity: 0, filter: 'blur(7px)' }} animate={{ opacity: 1, filter: 'blur(0px)' }} exit={{ opacity: 0, filter: 'blur(7px)' }} transition={{ duration: .3 }}><RouteScene {...route} liveState={liveState} socket={socket} profile={profile} onAuthenticated={authenticate} onLogout={logout} /></motion.div></AnimatePresence>
}
