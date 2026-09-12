import { motion } from 'framer-motion'
import { MapPin, Navigation } from 'lucide-react'

export function RumboMap({ locations = [], batch, className = '' }) {
  const route = batch?.route || []
  return <div className={`relative min-h-64 overflow-hidden rounded-3xl border border-cyan/20 bg-[#0c1420] ${className}`}>
    <div className="map-grid absolute inset-0 opacity-60" /><div className="scanline absolute inset-x-0 top-0 h-24 opacity-40" />
    <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Mapa vectorial de Monterrey">
      <path d="M5 78 C22 53, 29 58, 43 41 S69 18, 95 29" fill="none" stroke="rgba(148,163,184,.34)" strokeWidth=".8" />
      <path d="M-4 34 C23 28, 40 77, 103 62" fill="none" stroke="rgba(6,182,212,.28)" strokeWidth=".9" />
      {route.length > 1 && <motion.path initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1.4 }} d="M26 68 C42 58, 57 44, 75 32 S86 25, 92 23" fill="none" stroke="#06b6d4" strokeWidth="1.6" strokeLinecap="round" />}
    </svg>
    <div className="absolute left-[26%] top-[66%] flex -translate-x-1/2 -translate-y-1/2 items-center justify-center"><span className="orbital-ring absolute h-6 w-6 rounded-full" /><span className="relative rounded-full bg-violet p-1.5 shadow-glow"><Navigation size={13} /></span></div>
    {locations.map((location, index) => <div key={location.id || index} className="absolute" style={{ left: `${66 + index * 18}%`, top: `${42 - index * 16}%` }}><motion.div animate={{ scale: [1, 1.15, 1] }} transition={{ repeat: Infinity, duration: 2.1, delay: index * .3 }} className="rounded-full border border-cyan/60 bg-cyan/20 p-1.5 text-cyan shadow-cyan"><MapPin size={14} /></motion.div><span className="mt-1 block -translate-x-1/3 whitespace-nowrap text-[9px] font-medium text-white/70">{location.name || location.client_id}</span></div>)}
    <div className="absolute bottom-4 left-4 rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-[10px] tracking-[.12em] text-cyan/80 backdrop-blur">MONTERREY · EDGE ROUTE</div>
  </div>
}
