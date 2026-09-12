import { AnimatePresence, motion } from 'framer-motion'
import { useWebSocket } from './hooks/useWebSocket'
import { ClientExperience } from './rumbo/ClientExperience'
import { CommandCenter } from './rumbo/CommandCenter'
import { DriverHUD } from './rumbo/DriverHUD'
import { Landing } from './rumbo/Landing'
import { useRumboLive } from './rumbo/useRumboLive'
import { useRumboRoute } from './rumbo/useRumboRoute'

function RouteScene({ path, query, navigate, liveState, socket }) {
  const onHome = () => navigate('/')
  const connected = socket.status === 'connected'
  if (path === '/app/client') return <ClientExperience clientNumber={query.get('id')} live={liveState.live} connected={connected} send={socket.send} onHome={onHome} />
  if (path === '/app/driver') return <DriverHUD live={liveState.live} notification={liveState.notification} onDismiss={liveState.dismissNotification} connected={connected} send={socket.send} onHome={onHome} />
  if (path === '/app/dashboard') return <CommandCenter live={liveState.live} simulation={liveState.simulation} connected={connected} onTrigger={liveState.trigger} onStart={liveState.startDemo} onHome={onHome} />
  return <Landing onNavigate={navigate} />
}

export default function App() {
  const route = useRumboRoute()
  const liveState = useRumboLive()
  const socket = useWebSocket(liveState.onMessage)
  const routeKey = `${route.path}:${route.query.get('id') || ''}`
  return <AnimatePresence mode="wait"><motion.div key={routeKey} initial={{ opacity: 0, filter: 'blur(7px)' }} animate={{ opacity: 1, filter: 'blur(0px)' }} exit={{ opacity: 0, filter: 'blur(7px)' }} transition={{ duration: .3 }}><RouteScene {...route} liveState={liveState} socket={socket} /></motion.div></AnimatePresence>
}
