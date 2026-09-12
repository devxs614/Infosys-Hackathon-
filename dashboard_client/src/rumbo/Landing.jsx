import { motion } from 'framer-motion'
import { ArrowRight, Bot, Gauge, MapPin, Navigation, Sparkles, UserRound } from 'lucide-react'
import { useState } from 'react'
import { GlassCard } from './GlassCard'
import { roles } from './data'

const icons = { MapPin, Navigation, Gauge, Sparkles }

function RoleCard({ role, selected, onSelect }) {
  const [tilt, setTilt] = useState({ x: 0, y: 0 })
  const Icon = icons[role.icon]
  return <motion.button type="button" onClick={() => onSelect(role)} onMouseMove={(event) => {
    const box = event.currentTarget.getBoundingClientRect()
    setTilt({ x: ((event.clientY - box.top) / box.height - .5) * -8, y: ((event.clientX - box.left) / box.width - .5) * 10 })
  }} onMouseLeave={() => setTilt({ x: 0, y: 0 })} animate={{ rotateX: tilt.x, rotateY: tilt.y, scale: selected ? 1.015 : 1 }} transition={{ type: 'spring', stiffness: 250, damping: 18 }} style={{ transformStyle: 'preserve-3d' }} className={`group relative overflow-hidden rounded-3xl border p-5 text-left transition ${selected ? 'border-cyan/70 bg-white/[.09] shadow-cyan' : 'border-white/10 bg-white/[.035] hover:border-white/30'}`}>
    <div className={`absolute inset-x-0 top-0 h-24 bg-gradient-to-br ${role.tint} opacity-30 blur-2xl transition group-hover:opacity-60`} />
    <div style={{ transform: 'translateZ(26px)' }} className="relative"><div className="mb-9 flex items-start justify-between"><span className="rounded-2xl border border-white/15 bg-black/20 p-3 text-white"><Icon size={20} /></span><span className="text-[10px] font-semibold uppercase tracking-[.18em] text-white/50">{role.place}</span></div><p className="text-lg font-semibold tracking-tight text-white">{role.name}</p><p className="mt-1 text-xs leading-5 text-white/55">{role.description}</p><div className="mt-5 flex items-center gap-2 text-[11px] text-white/70"><UserRound size={13} /> {role.user} · demo access</div></div>
  </motion.button>
}

export function Landing({ onNavigate }) {
  const [selected, setSelected] = useState(roles[0])
  const [username, setUsername] = useState(roles[0].user)
  const [password, setPassword] = useState(roles[0].pass)
  const [error, setError] = useState('')
  const choose = (role) => { setSelected(role); setUsername(role.user); setPassword(role.pass); setError('') }
  const submit = (event) => {
    event.preventDefault()
    const match = roles.find((role) => role.user === username.trim() && role.pass === password)
    if (!match) return setError('Acceso de demo no reconocido. Selecciona un perfil Rumbo.')
    onNavigate(match.route)
  }
  return <main className="rumbo-noise relative min-h-screen overflow-hidden bg-ink px-5 py-6 sm:px-8 lg:px-12"><div className="grid-fade pointer-events-none absolute inset-x-0 top-0 h-[480px] opacity-60" />
    <header className="relative mx-auto flex max-w-7xl items-center justify-between"><div className="flex items-center gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-violet to-cyan shadow-glow"><Navigation size={20} /></div><div><p className="text-sm font-semibold tracking-tight">Rumbo</p><p className="text-[10px] tracking-[.16em] text-white/45">EDGE LOGISTICS OS</p></div></div><div className="glass rounded-full px-4 py-2 text-xs text-white/55">Monterrey, MX <span className="ml-2 text-cyan">● Online</span></div></header>
    <section className="relative mx-auto grid max-w-7xl gap-8 py-16 lg:grid-cols-[1.22fr_.78fr] lg:py-24"><div><motion.p initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="eyebrow">RUMBO / LIVE DEMO</motion.p><motion.h1 initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: .08 }} className="mt-4 max-w-3xl text-5xl font-semibold leading-[.94] tracking-[-.07em] text-white sm:text-7xl">La última milla,<br /><span className="bg-gradient-to-r from-violet via-fuchsia-300 to-cyan bg-clip-text text-transparent">en perfecta sincronía.</span></motion.h1><p className="mt-7 max-w-xl text-base leading-7 text-white/55">Una experiencia de logística viva: clientes, courier y la inteligencia Edge de Rumbo comparten una sola decisión, en tiempo real.</p>
        <div className="mt-10 grid gap-3 sm:grid-cols-2">{roles.map((role) => <RoleCard key={role.id} role={role} selected={role.id === selected.id} onSelect={choose} />)}</div>
      </div>
      <GlassCard delay={.18} className="h-fit p-6 sm:p-8 lg:sticky lg:top-10"><div className="mb-9 flex items-center gap-3"><div className="rounded-2xl border border-cyan/30 bg-cyan/10 p-3 text-cyan"><Bot size={21} /></div><div><p className="text-sm font-medium">Acceso Rumbo</p><p className="mt-1 text-xs text-white/45">Elige un rol para continuar</p></div></div><form onSubmit={submit} className="space-y-4"><label className="block text-xs text-white/50">Usuario<input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" className="mt-2 w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm outline-none transition focus:border-cyan/60" /></label><label className="block text-xs text-white/50">Contraseña<input value={password} onChange={(e) => setPassword(e.target.value)} type="password" autoComplete="current-password" className="mt-2 w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm outline-none transition focus:border-cyan/60" /></label>{error && <p className="rounded-2xl border border-rose-400/20 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">{error}</p>}<button className="app-button-primary w-full py-3.5">Entrar como {selected.name}<ArrowRight size={16} /></button></form><p className="mt-6 text-center text-[10px] leading-5 text-white/35">Credenciales de demo locales. El backend valida pedidos y acciones en la Raspberry Pi.</p></GlassCard>
    </section>
  </main>
}
