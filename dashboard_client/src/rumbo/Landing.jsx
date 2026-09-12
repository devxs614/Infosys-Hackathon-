import { motion } from 'framer-motion'
import { ArrowRight, Compass, Mail, ShieldCheck, Sparkles, Truck, UserRound } from 'lucide-react'
import { useState } from 'react'
import { GlassCard } from './GlassCard'

const profilesKey = 'rumbo.profiles'

function idFor(email, role) {
  const safe = email.toLowerCase().replace(/[^a-z0-9]/g, '-').replace(/-+/g, '-').slice(0, 42) || 'rumbo-user'
  return `${role}-${safe}-${Math.random().toString(36).slice(2, 7)}`
}

function storedProfiles() {
  try { return JSON.parse(window.localStorage.getItem(profilesKey) || '[]') } catch { return [] }
}

export function Landing({ onAuthenticated }) {
  const [role, setRole] = useState('client')
  const [flow, setFlow] = useState('register')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const submit = (event) => {
    event.preventDefault()
    const normalizedEmail = email.trim().toLowerCase()
    if (!normalizedEmail.includes('@') || password.trim().length < 3 || (flow === 'register' && name.trim().length < 2)) {
      return setError('Completa nombre, correo y una contraseña de al menos 3 caracteres.')
    }
    const profiles = storedProfiles()
    const existing = profiles.find((item) => item.email === normalizedEmail && item.role === role)
    if (flow === 'login' && (!existing || existing.password !== password)) return setError('No encontramos esa sesión local. Regístrate o usa una demo.')
    const next = flow === 'login' ? existing : { id: idFor(normalizedEmail, role), name: name.trim(), email: normalizedEmail, role, password }
    if (flow === 'register') window.localStorage.setItem(profilesKey, JSON.stringify([...profiles.filter((item) => !(item.email === normalizedEmail && item.role === role)), next]))
    const { password: _password, ...publicProfile } = next
    onAuthenticated(publicProfile)
  }
  const enterDemo = (demoRole) => onAuthenticated({
    id: `${demoRole}-demo-${Math.random().toString(36).slice(2, 7)}`,
    name: demoRole === 'driver' ? 'Alex · Courier Demo' : 'Sofía · Cliente Demo',
    email: `${demoRole}.demo@rumbo.local`, role: demoRole,
  })
  return <main className="rumbo-noise min-h-screen overflow-hidden bg-ink px-5 py-6 sm:px-8">
    <div className="mx-auto flex max-w-7xl items-center justify-between"><div className="flex items-center gap-3"><span className="rounded-2xl bg-gradient-to-br from-violet to-cyan p-2.5 shadow-glow"><Compass size={20} /></span><div><p className="font-semibold tracking-tight">Rumbo</p><p className="text-[9px] tracking-[.2em] text-white/45">EDGE LOGISTICS OS</p></div></div><div className="hidden items-center gap-2 text-xs text-white/50 sm:flex"><ShieldCheck size={15} className="text-cyan" />Raspberry Pi · live mesh</div></div>
    <section className="mx-auto grid max-w-7xl items-center gap-10 py-12 lg:grid-cols-[1.08fr_.92fr] lg:py-20"><div className="relative"><div className="grid-fade absolute -inset-10 opacity-70" /><motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="relative"><p className="eyebrow">MONTERREY · DELIVERY INTELLIGENCE</p><h1 className="mt-5 max-w-3xl text-5xl font-semibold leading-[.93] tracking-[-.075em] sm:text-7xl">La ciudad se mueve<br /><span className="bg-gradient-to-r from-violet-300 via-white to-cyan bg-clip-text text-transparent">con Rumbo.</span></h1><p className="mt-7 max-w-xl text-sm leading-7 text-white/55">Una red logística local diseñada para pedidos, couriers y decisiones Edge en tiempo real. Crea tu acceso en segundos: no hay cupos ni perfiles predeterminados.</p><div className="mt-10 grid max-w-xl grid-cols-3 gap-3"><div className="glass rounded-3xl p-4"><p className="text-2xl font-semibold tracking-tight text-cyan">120×</p><p className="mt-1 text-[10px] leading-4 text-white/45">Time warp<br />operativo</p></div><div className="glass rounded-3xl p-4"><p className="text-2xl font-semibold tracking-tight text-violet-300">OSRM</p><p className="mt-1 text-[10px] leading-4 text-white/45">Calles reales<br />de Monterrey</p></div><div className="glass rounded-3xl p-4"><p className="text-2xl font-semibold tracking-tight text-white">Live</p><p className="mt-1 text-[10px] leading-4 text-white/45">Multi-laptop<br />WebSocket</p></div></div></motion.div></div>
      <GlassCard delay={.12} className="relative overflow-hidden p-6 sm:p-8"><div className="absolute -right-16 -top-16 h-44 w-44 rounded-full bg-cyan/20 blur-3xl" /><div className="relative"><div className="flex rounded-2xl border border-white/10 bg-black/20 p-1"><button onClick={() => { setRole('client'); setError('') }} className={`flex-1 rounded-xl px-3 py-2.5 text-xs font-medium transition ${role === 'client' ? 'bg-white/10 text-white shadow-sm' : 'text-white/45'}`}><UserRound className="mr-2 inline" size={15} />Cliente</button><button onClick={() => { setRole('driver'); setError('') }} className={`flex-1 rounded-xl px-3 py-2.5 text-xs font-medium transition ${role === 'driver' ? 'bg-white/10 text-white shadow-sm' : 'text-white/45'}`}><Truck className="mr-2 inline" size={15} />Repartidor</button></div><div className="mt-6 flex gap-5 border-b border-white/10"><button onClick={() => { setFlow('register'); setError('') }} className={`pb-3 text-xs ${flow === 'register' ? 'border-b-2 border-cyan text-white' : 'text-white/45'}`}>Registro rápido</button><button onClick={() => { setFlow('login'); setError('') }} className={`pb-3 text-xs ${flow === 'login' ? 'border-b-2 border-cyan text-white' : 'text-white/45'}`}>Iniciar sesión</button></div><form onSubmit={submit} className="mt-6 space-y-3">{flow === 'register' && <label className="block"><span className="mb-1.5 block text-[10px] font-medium tracking-[.14em] text-white/45">NOMBRE</span><input value={name} onChange={(event) => setName(event.target.value)} placeholder="Carlos Treviño" className="rumbo-input" autoComplete="name" /></label>}<label className="block"><span className="mb-1.5 flex items-center gap-1.5 text-[10px] font-medium tracking-[.14em] text-white/45"><Mail size={12} />CORREO</span><input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="tu@correo.com" className="rumbo-input" autoComplete="email" /></label><label className="block"><span className="mb-1.5 block text-[10px] font-medium tracking-[.14em] text-white/45">CONTRASEÑA</span><input value={password} onChange={(event) => setPassword(event.target.value)} placeholder="••••••••" type="password" className="rumbo-input" autoComplete={flow === 'register' ? 'new-password' : 'current-password'} /></label>{error && <p className="text-xs text-rose-300">{error}</p>}<button className="app-button-primary mt-2 w-full py-3.5">{flow === 'register' ? 'Crear acceso Rumbo' : 'Entrar a Rumbo'} <ArrowRight size={16} /></button></form><div className="my-5 flex items-center gap-3 text-[10px] text-white/30"><i className="h-px flex-1 bg-white/10" />o entra directo<i className="h-px flex-1 bg-white/10" /></div><div className="grid gap-2 sm:grid-cols-2"><button onClick={() => enterDemo('client')} className="app-button py-3 text-xs"><Sparkles size={15} />Cliente Demo</button><button onClick={() => enterDemo('driver')} className="app-button py-3 text-xs"><Truck size={15} />Driver Demo</button></div><p className="mt-5 text-center text-[10px] leading-4 text-white/35">La sesión se guarda en este navegador. Tu contraseña no se transmite al Edge node.</p></div></GlassCard>
    </section>
  </main>
}
