import { motion } from 'framer-motion'
import { ArrowRight, Compass, Mail, ShieldCheck, Truck, UserRound } from 'lucide-react'
import { useState } from 'react'
import { authApi } from '../services/api'
import { GlassCard } from './GlassCard'
import { JudgesControlPanel } from './ProtocolSuite'

export function Landing({ onAuthenticated, protocol, onLaunchFullDemo }) {
  const [role, setRole] = useState('client')
  const [flow, setFlow] = useState('register')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [vehicle, setVehicle] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [launchingDemo, setLaunchingDemo] = useState(false)
  const [demoNotice, setDemoNotice] = useState('')
  const submit = async (event) => {
    event.preventDefault()
    const normalizedEmail = email.trim().toLowerCase()
    if (!normalizedEmail.includes('@') || password.trim().length < 3 || (flow === 'register' && name.trim().length < 2)) {
      return setError('Please provide a name, email, and password of at least 3 characters.')
    }
    setSubmitting(true)
    setError('')
    try {
      const result = flow === 'register'
        ? await authApi.register({ name: name.trim(), email: normalizedEmail, password, role, vehicle: role === 'driver' ? vehicle.trim() || null : null })
        : await authApi.login({ email: normalizedEmail, password })
      onAuthenticated({ ...result.user, session_token: result.session_token })
    } catch (caught) {
      setError(caught.message || 'Unable to authenticate with the Rumbo Edge server.')
    } finally {
      setSubmitting(false)
    }
  }
  const launchDemo = async () => {
    if (!onLaunchFullDemo || launchingDemo) return
    setLaunchingDemo(true)
    try {
      await onLaunchFullDemo()
      setDemoNotice('Full autonomous demo is now running on the Raspberry Pi: 15 clients and 7 couriers.')
    } catch (caught) {
      setDemoNotice(caught.message || 'Unable to start the Pi demo.')
    } finally {
      setLaunchingDemo(false)
    }
  }
  return <main className="rumbo-noise min-h-screen overflow-hidden bg-ink px-5 py-6 sm:px-8">
    <div className="mx-auto flex max-w-7xl items-center justify-between"><div className="flex items-center gap-3"><span className="rounded-2xl bg-gradient-to-br from-violet to-cyan p-2.5 shadow-glow"><Compass size={20} /></span><div><p className="font-semibold tracking-tight">Rumbo</p><p className="text-[9px] tracking-[.2em] text-white/45">EDGE LOGISTICS OS</p></div></div><div className="hidden items-center gap-2 text-xs text-white/50 sm:flex"><ShieldCheck size={15} className="text-cyan" />Raspberry Pi · live mesh</div></div>
    <section className="mx-auto grid max-w-7xl items-center gap-10 py-12 lg:grid-cols-[1.08fr_.92fr] lg:py-20"><div className="relative"><div className="grid-fade absolute -inset-10 opacity-70" /><motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="relative"><p className="eyebrow">MONTERREY · DELIVERY INTELLIGENCE</p><h1 className="mt-5 max-w-3xl text-5xl font-semibold leading-[.93] tracking-[-.075em] sm:text-7xl">La ciudad se mueve<br /><span className="bg-gradient-to-r from-violet-300 via-white to-cyan bg-clip-text text-transparent">con Rumbo.</span></h1><p className="mt-7 max-w-xl text-sm leading-7 text-white/55">Una red logística local diseñada para pedidos, couriers y decisiones Edge en tiempo real. Crea tu acceso en segundos: no hay cupos ni perfiles predeterminados.</p><div className="mt-10 grid max-w-xl grid-cols-3 gap-3"><div className="glass rounded-3xl p-4"><p className="text-2xl font-semibold tracking-tight text-cyan">120×</p><p className="mt-1 text-[10px] leading-4 text-white/45">Time warp<br />operativo</p></div><div className="glass rounded-3xl p-4"><p className="text-2xl font-semibold tracking-tight text-violet-300">OSRM</p><p className="mt-1 text-[10px] leading-4 text-white/45">Calles reales<br />de Monterrey</p></div><div className="glass rounded-3xl p-4"><p className="text-2xl font-semibold tracking-tight text-white">Live</p><p className="mt-1 text-[10px] leading-4 text-white/45">Multi-laptop<br />WebSocket</p></div></div></motion.div></div>
      <GlassCard delay={.12} className="relative overflow-hidden p-6 sm:p-8"><div className="absolute -right-16 -top-16 h-44 w-44 rounded-full bg-cyan/20 blur-3xl" /><div className="relative"><div className="flex rounded-2xl border border-white/10 bg-black/20 p-1"><button onClick={() => { setRole('client'); setError('') }} className={`flex-1 rounded-xl px-3 py-2.5 text-xs font-medium transition ${role === 'client' ? 'bg-white/10 text-white shadow-sm' : 'text-white/45'}`}><UserRound className="mr-2 inline" size={15} />Customer</button><button onClick={() => { setRole('driver'); setError('') }} className={`flex-1 rounded-xl px-3 py-2.5 text-xs font-medium transition ${role === 'driver' ? 'bg-white/10 text-white shadow-sm' : 'text-white/45'}`}><Truck className="mr-2 inline" size={15} />Courier</button></div><div className="mt-6 flex gap-5 border-b border-white/10"><button onClick={() => { setFlow('register'); setError('') }} className={`pb-3 text-xs ${flow === 'register' ? 'border-b-2 border-cyan text-white' : 'text-white/45'}`}>Register</button><button onClick={() => { setFlow('login'); setError('') }} className={`pb-3 text-xs ${flow === 'login' ? 'border-b-2 border-cyan text-white' : 'text-white/45'}`}>Sign in</button></div><form onSubmit={submit} className="mt-6 space-y-3">{flow === 'register' && <label className="block"><span className="mb-1.5 block text-[10px] font-medium tracking-[.14em] text-white/45">NAME</span><input value={name} onChange={(event) => setName(event.target.value)} placeholder="Your name" className="rumbo-input" autoComplete="name" /></label>}{flow === 'register' && role === 'driver' && <label className="block"><span className="mb-1.5 block text-[10px] font-medium tracking-[.14em] text-white/45">VEHICLE</span><input value={vehicle} onChange={(event) => setVehicle(event.target.value)} placeholder="Your registered vehicle" className="rumbo-input" autoComplete="off" /></label>}<label className="block"><span className="mb-1.5 flex items-center gap-1.5 text-[10px] font-medium tracking-[.14em] text-white/45"><Mail size={12} />EMAIL</span><input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@email.com" className="rumbo-input" autoComplete="email" /></label><label className="block"><span className="mb-1.5 block text-[10px] font-medium tracking-[.14em] text-white/45">PASSWORD</span><input value={password} onChange={(event) => setPassword(event.target.value)} placeholder="••••••••" type="password" className="rumbo-input" autoComplete={flow === 'register' ? 'new-password' : 'current-password'} /></label>{error && <p className="text-xs text-rose-300">{error}</p>}<button disabled={submitting} className="app-button-primary mt-2 w-full py-3.5 disabled:cursor-not-allowed disabled:opacity-50">{submitting ? 'Connecting…' : flow === 'register' ? 'Create Rumbo access' : 'Sign in to Rumbo'} <ArrowRight size={16} /></button></form><div className="mt-5 border-t border-white/10 pt-5"><button onClick={launchDemo} disabled={launchingDemo} className="app-button w-full border-cyan/35 bg-cyan/10 text-xs text-cyan disabled:opacity-50">{launchingDemo ? 'Launching Pi demo…' : 'Launch Full Autonomous Demo (15 Clients + 7 Couriers)'}</button>{demoNotice && <p className="mt-3 text-xs leading-5 text-cyan/85">{demoNotice}</p>}</div><p className="mt-5 text-center text-[10px] leading-4 text-white/35">Accounts are stored and validated only by the Raspberry Pi Edge server.</p></div></GlassCard>
    </section><JudgesControlPanel protocol={protocol} />
  </main>
}
