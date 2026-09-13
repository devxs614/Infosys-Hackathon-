import { AnimatePresence, motion } from 'framer-motion'
import { CheckCircle2, Clock3, Sparkles, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

/** Client-only acknowledgement shown when ORDER_MATCHED arrives from the Pi. */
export function ClientAssignmentModal({ assignment }) {
  const [visible, setVisible] = useState(false)
  const shownOrderId = useRef(null)
  useEffect(() => {
    const orderId = assignment?.order?.id
    if (orderId && orderId !== shownOrderId.current) {
      shownOrderId.current = orderId
      setVisible(true)
    }
  }, [assignment?.order?.id])
  const driver = assignment?.driver
  if (!driver) return null
  const eta = Math.max(1, Math.round(assignment.order?.courier_eta_minutes ?? assignment.order?.eta_minutes ?? 0))
  return <AnimatePresence>{visible && <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-[1200] flex items-center justify-center bg-black/55 p-5 backdrop-blur-md">
    <motion.section initial={{ opacity: 0, y: 22, scale: .95 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 14, scale: .96 }} transition={{ type: 'spring', stiffness: 260, damping: 22 }} className="relative w-full max-w-md overflow-hidden rounded-[2rem] border border-cyan/40 bg-[#101522]/95 p-7 shadow-2xl">
      <motion.div animate={{ opacity: [.15, .8, .15], scale: [.9, 1.15, .9] }} transition={{ duration: 1.1, repeat: 2 }} className="pointer-events-none absolute -right-12 -top-12 h-40 w-40 rounded-full bg-cyan/40 blur-3xl" />
      <motion.div animate={{ boxShadow: ['0 0 0 rgba(6,182,212,0)', '0 0 58px rgba(6,182,212,.45)', '0 0 0 rgba(6,182,212,0)'] }} transition={{ duration: .78, repeat: 2 }} className="relative">
        <button onClick={() => setVisible(false)} className="absolute right-0 top-0 text-white/45 transition hover:text-white" aria-label="Cerrar"><X size={18} /></button>
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-cyan/20 text-cyan"><CheckCircle2 size={30} /></div>
        <p className="eyebrow mt-5">RUMBO EDGE CONFIRMATION</p>
        <h2 className="mt-2 text-3xl font-semibold tracking-[-.06em]">¡Repartidor asignado!</h2>
        <p className="mt-3 text-sm leading-6 text-white/55">Tu pedido ya tiene una ruta optimizada y un courier confirmado.</p>
        <div className="mt-6 flex items-center gap-4 rounded-3xl border border-white/10 bg-white/[.055] p-4">
          {driver.avatar_url ? <img src={driver.avatar_url} alt="" className="h-14 w-14 rounded-2xl object-cover" /> : <div className="grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-violet to-cyan text-lg font-semibold">{driver.name?.slice(0, 1)}</div>}
          <div className="min-w-0 flex-1"><p className="truncate font-semibold">{driver.name}</p>{driver.vehicle && <p className="mt-1 text-xs text-white/55">{driver.vehicle}</p>}</div>
          <div className="text-right"><Clock3 className="ml-auto text-cyan" size={17} /><p className="mt-1 text-lg font-semibold text-cyan">{eta} min</p></div>
        </div>
        <div className="mt-5 flex items-center gap-2 text-xs text-violet-200"><Sparkles size={15} />Sincronizado con la Raspberry Pi en tiempo real.</div>
        <button onClick={() => setVisible(false)} className="app-button-primary mt-6 w-full py-3">Ver rastreo en vivo</button>
      </motion.div>
    </motion.section>
  </motion.div>}</AnimatePresence>
}
