import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { ClientExperience, NoCouriersModal } from './rumbo/ClientExperience'
import { ClientAssignmentModal } from './rumbo/ClientAssignmentModal'
import { CommandCenter } from './rumbo/CommandCenter'
import { DriverHUD } from './rumbo/DriverHUD'
import { Landing } from './rumbo/Landing'
import { DriverVehicleSelector, JudgeDashboardDock, ProtocolShiftClock, useProtocolShift } from './rumbo/ProtocolSuite'
import { useRumboLive } from './rumbo/useRumboLive'
import { useRumboRoute } from './rumbo/useRumboRoute'

const sessionKey = 'rumbo.active-session'

// Presentation-only localization. Keep transport payloads and routing contracts unchanged.
const englishCopy = [
  ['¡Repartidor asignado!', 'Courier assigned!'], ['RUMBO EDGE CONFIRMATION', 'RUMBO EDGE CONFIRMATION'],
  ['La ciudad se mueve', 'The city moves'], ['con Rumbo.', 'with Rumbo.'],
  ['Una red logística local diseñada para pedidos, couriers y decisiones Edge en tiempo real. Crea tu acceso en segundos: no hay cupos ni perfiles predeterminados.', 'A local logistics network for orders, couriers, and real-time Edge decisions. Create your access in seconds: there are no fixed profiles or capacity limits.'],
  ['Time warp operativo', 'Operational time warp'], ['Calles reales de Monterrey', 'Real streets of Monterrey'], ['o entra directo', 'or enter directly'],
  ['Salmón, yuzu y aguacate', 'Salmon, yuzu, and avocado'], ['Selección de temporada', 'Seasonal selection'],
  ['La sesión se guarda en este navegador. Tu contraseña no se transmite al Edge node.', 'Your session is stored in this browser. Your password is never sent to the Edge node.'],
  ['Completa nombre, correo y una contraseña de al menos 3 caracteres.', 'Enter your name, email, and a password with at least 3 characters.'],
  ['No encontramos esa sesión local. Regístrate o usa una demo.', 'We could not find that local session. Register or use a demo account.'],
  ['Registro rápido', 'Quick registration'], ['Iniciar sesión', 'Sign in'], ['Crear acceso Rumbo', 'Create Rumbo access'], ['Entrar a Rumbo', 'Enter Rumbo'],
  ['Cliente Demo', 'Customer Demo'], ['Cliente', 'Customer'], ['Repartidor', 'Courier'], ['NOMBRE', 'NAME'], ['CORREO', 'EMAIL'], ['CONTRASEÑA', 'PASSWORD'],
  ['Hola, ', 'Hello, '], ['Salir', 'Sign out'], ['PEDIDO', 'ORDER'], ['Tu ruta está', 'Your route is'], ['conectada.', 'connected.'],
  ['COURIER → TIENDA', 'COURIER → STORE'], ['TIENDA → TU DIRECCIÓN', 'STORE → YOUR ADDRESS'], ['Buscando un repartidor registrado cercano…', 'Finding a nearby registered courier…'],
  ['Repartidor asignado:', 'Assigned courier:'], ['Solo se mostrarán couriers que se hayan registrado y estén en línea.', 'Only registered, online couriers are shown.'],
  ['ESTADO DE LA RED', 'NETWORK STATUS'], ['Gemini Edge mantiene la secuencia del recorrido compartido.', 'Gemini Edge is maintaining the shared route sequence.'],
  ['Rumbo eligió al courier registrado con menor distancia a la tienda.', 'Rumbo selected the registered courier closest to the store.'], ['Cancelando…', 'Cancelling…'], ['Cancelar pedido', 'Cancel order'],
  ['PUNTO DE ENTREGA', 'DELIVERY LOCATION'], ['Tu dirección exacta', 'Your exact address'], ['Busca en Monterrey', 'Search Monterrey'], ['Arrastra el pin o toca el mapa para indicar la puerta exacta.', 'Drag the pin or tap the map to set the exact delivery point.'],
  ['ORIGEN', 'ORIGIN'], ['RESUMEN UBER-STYLE', 'UBER-STYLE SUMMARY'], ['Platillo', 'Item'], ['Envío Edge', 'Edge delivery'], ['Calculando…', 'Calculating…'], ['Pedir con Rumbo AI', 'Order with Rumbo AI'], ['Conecta la Raspberry Pi para confirmar.', 'Connect to the Raspberry Pi to confirm.'],
  ['Ruta de calle, no estimación visual.', 'Street route, not a visual estimate.'], ['OSRM trazó la ruta sobre la red vial real de Monterrey.', 'OSRM mapped the route on Monterrey’s real street network.'], ['La Raspberry Pi está preparando una ruta local de respaldo.', 'The Raspberry Pi is preparing a local fallback route.'],
  ['En espera de asignación', 'Waiting for assignment'], ['DISTANCIA', 'DISTANCE'], ['VELOCIDAD', 'SPEED'], ['CALLE ACTUAL', 'CURRENT STREET'], ['MISIÓN ACTIVA', 'ACTIVE MISSION'],
  ['La mejor misión llega a ti.', 'Your next great mission is on its way.'], ['Asignación por proximidad Edge.', 'Edge proximity assignment.'], ['ACCIONES EN VIVO', 'LIVE ACTIONS'], ['Aceptar Batch', 'Accept batch'], ['Aceptar asignación', 'Accept assignment'], ['Llegué a Restaurante', 'Arrived at restaurant'], ['Marcar entregado', 'Mark delivered'], ['Courier en línea', 'Courier online'], ['Registrando enlace', 'Registering connection'], ['Telemetría Edge actualizada con orientación real de la calle.', 'Edge telemetry updated with real street direction.'], ['ACTUALIZACIÓN DE MISIÓN', 'MISSION UPDATE'], ['Ver en navegación', 'View in navigation'],
  ['Tu operación, en números.', 'Your operation, by the numbers.'], ['GANANCIA DE ESTE VIAJE', 'TRIP EARNINGS'], ['Base + distancia Edge', 'Base + Edge distance'], ['ACUMULADO HOY', 'TODAY’S TOTAL'], ['Entregas confirmadas', 'Confirmed deliveries'], ['Ahorro con Rumbo AI:', 'Rumbo AI savings:'], ['calculando', 'calculating'], ['y ', 'and '], ['menos distancia gracias al batching.', 'less distance thanks to batching.'],
  ['El dictamen de Rumbo Edge', 'Rumbo Edge verdict'], ['TIEMPO TOTAL AHORRADO', 'TOTAL TIME SAVED'], ['COMBUSTIBLE / KM REDUCIDOS', 'FUEL / KM REDUCED'], ['Esperando dos pedidos próximos para emitir un veredicto financiero verificable.', 'Waiting for two nearby orders to produce a verifiable financial verdict.'],
  ['Simulación activa', 'Simulation active'], ['Iniciar demo', 'Start demo'], ['La operación completa,', 'The entire operation,'], ['en una sola superficie.', 'on one surface.'], ['Usuarios y couriers entran desde cualquier laptop. El Edge node calcula rutas, pagos, batches y telemetría desde la Raspberry Pi.', 'Users and couriers join from any laptop. The Edge node calculates routes, payments, batches, and telemetry on the Raspberry Pi.'], ['Esperando pedidos desde la red', 'Waiting for orders from the network'], ['PEDIDOS LIVE', 'LIVE ORDERS'], ['GANANCIAS AI', 'AI EARNINGS'], ['MEJORA IA', 'AI IMPROVEMENT'], ['REPARTIDORES ACTIVOS', 'ACTIVE COURIERS'], ['La flota en vivo', 'Live fleet'], ['ESTADO', 'STATUS'], ['ENTREGAS', 'DELIVERIES'], ['GANANCIAS', 'EARNINGS'], ['Esperando repartidores registrados.', 'Waiting for registered couriers.'], ['Flujo de valor', 'Value flow'], ['INGRESOS TOTALES PLATAFORMA', 'TOTAL PLATFORM REVENUE'], ['Comisión retenida', 'Commission retained'], ['PAGO TOTAL A REPARTIDORES', 'TOTAL COURIER PAYOUT'], ['TRÁFICO', 'TRAFFIC'], ['CLIMA', 'WEATHER'], ['MINUTO SIM.', 'SIM. MINUTE'], ['SIMULADOR PARA JUECES', 'JUDGE SIMULATOR'], ['Eventos que cambian la decisión Edge', 'Events that change the Edge decision'], ['Lluvia torrencial', 'Torrential rain'], ['Inundación Gonzalitos', 'Gonzalitos flooding'], ['Congestionamiento San Pedro', 'San Pedro congestion'],
  ['Buscando courier', 'Finding courier'], ['Courier asignado', 'Courier assigned'], ['En ruta', 'On route'], ['Entregado', 'Delivered'], ['Origen · Rumbo Kitchen', 'Origin · Rumbo Kitchen'], ['Entrega', 'Delivery'], ['ÁMBAR · COURIER → TIENDA  ·  VIOLETA · TIENDA → CLIENTE', 'AMBER · COURIER → STORE  ·  VIOLET · STORE → CUSTOMER'],
  ['Nuevo pedido asignado', 'New order assigned'], ['Pedido cancelado por el cliente', 'Order cancelled by customer'], ['Rumbo AI detectó un batch', 'Rumbo AI detected a batch'], ['Rumbo Edge espera pedidos cercanos para evaluar un batching real.', 'Rumbo Edge is waiting for nearby orders to evaluate a real batch.'], ['Rumbo Edge agrupó los destinos cercanos de', 'Rumbo Edge grouped the nearby destinations of'], ['Ahorro calculado:', 'Calculated saving:'], ['✅ DECISIÓN OPTIMAL:', '✅ OPTIMAL DECISION:'], ['El Batching incrementó la ganancia proyectada del courier un', 'Batching increased the courier’s projected earnings by'], ['y redujo', 'and reduced'], ['min de operación.', 'minutes of operation.'], ['Rumbo Edge reportó un error.', 'Rumbo Edge reported an error.'],
  ['No hay repartidores disponibles en este momento', 'No couriers are available right now'], ['La dirección de entrega excede el límite operativo de 20 km', 'The delivery address exceeds the 20 km operating limit'],
]

function toEnglish(value) {
  return englishCopy.reduce((translated, [spanish, english]) => translated.replaceAll(spanish, english), value)
}

function EnglishPage() {
  useEffect(() => {
    document.documentElement.lang = 'en'
    const translate = (root = document.body) => {
      const textNodes = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
      const nodes = []
      while (textNodes.nextNode()) nodes.push(textNodes.currentNode)
      nodes.forEach((node) => {
        const translated = toEnglish(node.nodeValue)
        if (translated !== node.nodeValue) node.nodeValue = translated
      })
      root.querySelectorAll('[placeholder], [aria-label], [title]').forEach((element) => {
        ;['placeholder', 'aria-label', 'title'].forEach((attribute) => {
          const value = element.getAttribute(attribute)
          if (value) element.setAttribute(attribute, toEnglish(value))
        })
      })
    }
    translate()
    const observer = new MutationObserver(() => translate())
    observer.observe(document.body, { childList: true, characterData: true, subtree: true })
    return () => observer.disconnect()
  }, [])
  return null
}

function readSession() {
  try { return JSON.parse(window.localStorage.getItem(sessionKey) || 'null') } catch { return null }
}

function RouteScene({ path, query, navigate, liveState, socket, profile, onAuthenticated, onLogout, protocol }) {
  const onHome = () => navigate('/')
  const connected = socket.status === 'connected'
  if (path === '/app/client' && profile?.role === 'client') {
    const clientOrder = [...(liveState.live.orders || [])].reverse().find((order) => order.client_id === profile.id && ['PENDING', 'MATCHED', 'IN_TRANSIT'].includes(order.status))
    const assignment = clientOrder ? liveState.live.orderMatches?.[clientOrder.id] : null
    return <><ClientExperience profile={profile} live={liveState.live} connected={connected} send={socket.send} onHome={onHome} onLogout={onLogout} /><ClientAssignmentModal assignment={assignment} /><NoCouriersModal notice={liveState.live.noCouriersNotice} onDismiss={liveState.dismissNoCouriersNotice} /></>
  }
  if (path === '/app/driver' && profile?.role === 'driver') return <><DriverHUD profile={profile} live={liveState.live} notification={liveState.driverNotifications?.[profile.id] || liveState.notification} onDismiss={() => liveState.dismissNotification(profile.id)} connected={connected} send={socket.send} onHome={onHome} onLogout={onLogout} /><DriverVehicleSelector profile={profile} live={liveState.live} protocol={protocol} /></>
  if (path === '/app/dashboard') return <><CommandCenter profile={profile} live={liveState.live} simulation={liveState.simulation} connected={connected} onTrigger={liveState.trigger} onStart={liveState.startDemo} onHome={onHome} onLogout={onLogout} /><JudgeDashboardDock protocol={protocol} onTrigger={liveState.trigger} /></>
  return <Landing onAuthenticated={onAuthenticated} protocol={protocol} />
}

export default function App() {
  const route = useRumboRoute()
  const liveState = useRumboLive()
  const socket = useWebSocket(liveState.onMessage)
  const protocol = useProtocolShift()
  const [profile, setProfile] = useState(readSession)
  useEffect(() => {
    if (socket.status !== 'connected' || !profile?.session_token) return undefined
    if (profile.role === 'driver') return undefined
    socket.send({ type: 'REGISTER_USER', data: { user_id: profile.id, session_token: profile.session_token, location: null } })
    return undefined
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
  return <><EnglishPage /><ProtocolShiftClock protocol={protocol} /><AnimatePresence mode="wait"><motion.div key={routeKey} initial={{ opacity: 0, filter: 'blur(7px)' }} animate={{ opacity: 1, filter: 'blur(0px)' }} exit={{ opacity: 0, filter: 'blur(7px)' }} transition={{ duration: .3 }}><RouteScene {...route} liveState={liveState} socket={socket} profile={profile} onAuthenticated={authenticate} onLogout={logout} protocol={protocol} /></motion.div></AnimatePresence></>
}
