import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, Clock3, Download, FilePlay, Gauge, Pause, Play, ShieldAlert, Upload } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { decisionApi, demoApi } from '../services/api'
import { GlassCard } from './GlassCard'

export const vehicleProfiles = {
  moto: { label: 'Moto', icon: '🏍️', speed: 45, weight: 20, volume: 20 },
  car: { label: 'Car', icon: '🚗', speed: 35, weight: 150, volume: 200 },
  bike: { label: 'Bike', icon: '🚲', speed: 18, weight: 8, volume: 12 },
}

const defaultConfiguration = { seed: 42, shift_hours: 8.5, vehicle: 'moto', start_location_zone: 5 }

function formatClock(totalMinutes) {
  const normalized = ((Math.round(totalMinutes) % 1440) + 1440) % 1440
  return `${String(Math.floor(normalized / 60)).padStart(2, '0')}:${String(normalized % 60).padStart(2, '0')}`
}

function timeToMinutes(value) {
  const [hour = '0', minute = '0'] = String(value).split(':')
  return Number(hour) * 60 + Number(minute)
}

function broadcastVisualState(detail) {
  window.dispatchEvent(new CustomEvent('rumbo-protocol-visual', { detail }))
}

export function useProtocolShift() {
  const [configuration, setConfiguration] = useState(defaultConfiguration)
  const [simulatedMinutes, setSimulatedMinutes] = useState(14 * 60)
  const [paused, setPaused] = useState(false)
  const [degraded, setDegraded] = useState(false)
  const [shock, setShock] = useState(null)
  const [replay, setReplay] = useState(null)
  const [driverVehicles, setDriverVehicles] = useState({})
  const [closurePinMode, setClosurePinMode] = useState(false)

  useEffect(() => {
    let active = true
    demoApi.timeSync().then((state) => {
      if (!active) return
      setSimulatedMinutes(state.simulated_minutes)
      setPaused(Boolean(state.paused))
      setShock(state.shock || null)
    }).catch(() => {})
    return () => { active = false }
  }, [])

  useEffect(() => {
    broadcastVisualState({ simulatedMinutes, shock, vehicle: configuration.vehicle })
  }, [configuration.vehicle, shock, simulatedMinutes])

  const applyServerState = useCallback((state) => {
    if (!state || typeof state.simulated_minutes !== 'number') return
    setSimulatedMinutes(state.simulated_minutes)
    setPaused(Boolean(state.paused))
    setShock(state.shock || null)
  }, [])

  const configure = async (nextConfiguration) => {
    const normalized = { ...nextConfiguration, seed: Number(nextConfiguration.seed), shift_hours: Number(nextConfiguration.shift_hours), start_location_zone: Number(nextConfiguration.start_location_zone) }
    setConfiguration(normalized)
    try {
      const response = await demoApi.configure(normalized)
      return { ok: true, config: response.config }
    } catch (error) {
      return { ok: false, message: error.message }
    }
  }

  const toggleDegraded = async (enabled) => {
    setDegraded(enabled)
    try { await demoApi.setDegraded(enabled) } catch { /* Still show the fallback drill while disconnected. */ }
  }

  const selectVehicle = (driverId, vehicle) => {
    setDriverVehicles((current) => ({ ...current, [driverId]: vehicle }))
    broadcastVisualState({ simulatedMinutes, shock, vehicle })
  }

  const syncTime = useCallback(async (next) => {
    const state = await demoApi.updateTimeSync(next)
    applyServerState(state)
    return state
  }, [applyServerState])

  const setServerMinutes = useCallback((time) => {
    const simulated_minutes = typeof time === 'number' ? time : timeToMinutes(time)
    return syncTime({ simulated_minutes })
  }, [syncTime])

  const setServerPaused = useCallback((next) => syncTime({ paused: next }), [syncTime])

  const triggerShock = useCallback(async (kind, zone = null) => {
    const state = await demoApi.shock({ shock: kind, zone })
    applyServerState(state)
    return state
  }, [applyServerState])

  const pinRoadClosure = useCallback(async (position, label) => {
    const state = await demoApi.pinRoadClosure({ position, label })
    applyServerState(state)
    setClosurePinMode(false)
    return state
  }, [applyServerState])

  const delayDriver = useCallback(async (driver_id, minutes = 15) => {
    const response = await demoApi.delayDriver({ driver_id, minutes })
    applyServerState(response.control)
    return response
  }, [applyServerState])

  const onSocketMessage = useCallback((message) => {
    if (message.type === 'TIME_SYNC_UPDATE') applyServerState(message.data)
  }, [applyServerState])

  const launchFullDemo = useCallback(() => demoApi.launchFullAutonomousDemo(), [])

  return {
    configuration, simulatedMinutes, clock: formatClock(simulatedMinutes), paused, degraded, shock, replay, driverVehicles,
    closurePinMode, setClosurePinMode,
    setPaused: setServerPaused, setSimulatedMinutes: setServerMinutes,
    configure, toggleDegraded, setShock: triggerShock, setReplay, selectVehicle, triggerShock, pinRoadClosure, delayDriver, launchFullDemo, onSocketMessage,
  }
}

export function ProtocolShiftClock({ protocol }) {
  return <div className="protocol-clock pointer-events-none fixed left-1/2 top-3 z-[60] hidden -translate-x-1/2 items-center gap-3 rounded-2xl border border-cyan/25 bg-[#09090b]/90 px-3 py-2 shadow-2xl backdrop-blur-xl lg:flex"><Clock3 size={15} className="text-cyan" /><div><p className="text-[9px] font-semibold tracking-[.17em] text-white/45">SHIFT CLOCK · 15×</p><p className="font-mono text-sm font-semibold tracking-[.12em] text-cyan">{protocol.clock}</p></div><span className={`h-2 w-2 rounded-full ${protocol.paused ? 'bg-amber-300' : 'animate-pulse bg-emerald-300'}`} /></div>
}

export function JudgesControlPanel({ protocol }) {
  const [draft, setDraft] = useState(protocol.configuration)
  const [notice, setNotice] = useState('Configure a deterministic shift before starting the live demo.')
  const [playbackIndex, setPlaybackIndex] = useState(-1)
  const fileInput = useRef(null)
  const update = (key, value) => setDraft((current) => ({ ...current, [key]: value }))

  useEffect(() => {
    if (playbackIndex < 0 || !protocol.replay) return undefined
    const entry = protocol.replay.entries[playbackIndex]
    if (!entry) {
      setPlaybackIndex(-1)
      setNotice('Offline replay complete. Recorded event sequence was reproduced without an Edge request.')
      return undefined
    }
    if (entry.sim_time) {
      const timestamp = new Date(entry.sim_time)
      if (!Number.isNaN(timestamp.valueOf())) protocol.setSimulatedMinutes(timestamp.getHours() * 60 + timestamp.getMinutes())
    }
    if (entry.event === 'shock') protocol.setShock(entry.shock_type)
    const timer = window.setTimeout(() => setPlaybackIndex((current) => current + 1), 650)
    return () => window.clearTimeout(timer)
  }, [playbackIndex, protocol.replay])

  const applyConfiguration = async () => {
    const result = await protocol.configure(draft)
    setNotice(result.ok ? `Seed ${result.config.seed} is ready for deterministic playback.` : `Saved locally. Edge configuration will apply when connected: ${result.message}`)
  }

  const loadReplay = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    try {
      const entries = (await file.text()).split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line))
      const offers = entries.filter((entry) => entry.event === 'order_offered')
      const decisions = entries.filter((entry) => entry.event === 'decision')
      protocol.setReplay({ fileName: file.name, entries, offers, decisions, deterministic: offers.length === decisions.length || !decisions.length })
      setNotice(`Offline replay loaded: ${offers.length} order ping(s), ${decisions.length} recorded decision(s).`)
    } catch {
      setNotice('This file is not valid JSON Lines event-log data.')
    }
  }

  const exportResults = () => {
    const accepted = protocol.replay?.decisions.filter((entry) => entry.decision === 'ACCEPT').length || 0
    const rows = [
      ['AcceptAll', '', '', '', '', '', '', '', ''], ['HighestPay', '', '', '', '', '', '', '', ''],
      ['NearestFirst', '', '', '', '', '', '', '', ''], ['GreedyRate', '', '', '', '', '', '', '', ''],
      ['OurAgent', '', '', '', '', accepted, '', 0, 0], ['Oracle', '', '', '', '', '', '', '', ''],
    ]
    const header = 'policy,mean_earnings_mxn,median_earnings_mxn,mean_mxn_per_hr,accept_rate_pct,orders_completed,deadhead_pct_of_km,deadline_misses,safety_violations'
    const blob = new Blob([[header, ...rows.map((row) => row.join(','))].join('\n') + '\n'], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'results_table_template.csv'
    link.click()
    URL.revokeObjectURL(url)
    setNotice('Results table exported. Add 10 held-out shifts and retain zero safety violations before presenting it.')
  }

  return <GlassCard className="protocol-panel mx-auto mt-3 max-w-7xl p-5 sm:p-6"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="eyebrow">HACKMTY JUDGES CONTROL PANEL</p><h2 className="mt-2 text-xl font-semibold tracking-[-.04em]">Rehearse the evaluation protocol.</h2><p className="mt-2 max-w-2xl text-xs leading-5 text-white/50">Configuration, replay, and result reporting remain separate from customer accounts and the live courier mesh.</p></div><span className="rounded-2xl border border-cyan/25 bg-cyan/10 px-3 py-2 text-[10px] font-semibold tracking-[.14em] text-cyan">DETERMINISTIC FAST PATH</span></div><div className="mt-5 grid gap-3 lg:grid-cols-[1fr_1fr_1fr_auto]"><label><span className="mb-1 block text-[10px] tracking-[.14em] text-white/45">SEED</span><input className="rumbo-input py-2" type="number" value={draft.seed} onChange={(event) => update('seed', event.target.value)} /></label><label><span className="mb-1 block text-[10px] tracking-[.14em] text-white/45">SHIFT HOURS</span><select className="rumbo-input py-2" value={draft.shift_hours} onChange={(event) => update('shift_hours', event.target.value)}><option value="8">8.0</option><option value="8.5">8.5</option><option value="10">10.0</option></select></label><label><span className="mb-1 block text-[10px] tracking-[.14em] text-white/45">START ZONE</span><select className="rumbo-input py-2" value={draft.start_location_zone} onChange={(event) => update('start_location_zone', event.target.value)}>{[3, 5, 7, 11].map((zone) => <option key={zone} value={zone}>Zone {zone}</option>)}</select></label><button onClick={applyConfiguration} className="app-button-primary self-end py-2.5">Apply shift</button></div><div className="mt-3 flex flex-wrap gap-2"><button onClick={() => fileInput.current?.click()} className="app-button text-xs"><FilePlay size={15} />Run Determinism Test</button><input ref={fileInput} type="file" accept=".jsonl,application/json" className="hidden" onChange={loadReplay} /><button disabled={!protocol.replay || playbackIndex >= 0} onClick={() => { protocol.setPaused(true); setPlaybackIndex(0) }} className="app-button text-xs"><Play size={15} />Play offline replay</button><button onClick={exportResults} className="app-button text-xs"><Download size={15} />Export Held-out Results</button>{protocol.replay && <span className="inline-flex items-center rounded-2xl border border-emerald-300/20 bg-emerald-300/10 px-3 text-xs text-emerald-200"><Upload size={13} className="mr-2" />{protocol.replay.fileName} · offline {playbackIndex >= 0 ? `· event ${playbackIndex + 1}/${protocol.replay.entries.length}` : ''}</span>}</div><p className="mt-4 text-xs text-white/45">{notice}</p></GlassCard>
}

export function DriverVehicleSelector({ profile, live, protocol }) {
  const selected = protocol.driverVehicles[profile.id]
  const activeOrder = (live.orders || []).find((order) => order.driver_id === profile.id && !['DELIVERED', 'CANCELLED'].includes(order.status))
  const limits = selected ? vehicleProfiles[selected] : null
  const weight = Number(activeOrder?.weight_kg || 0)
  const volume = Number(activeOrder?.volume_liters || activeOrder?.volume_l || 0)
  const exceeded = limits && (weight > limits.weight || volume > limits.volume)
  return <AnimatePresence>{!selected && <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-[1450] grid place-items-center bg-black/70 p-5 backdrop-blur-md"><motion.div initial={{ y: 24, scale: .97 }} animate={{ y: 0, scale: 1 }} className="w-full max-w-2xl rounded-[2rem] border border-white/10 bg-[#101522]/95 p-6 shadow-2xl"><p className="eyebrow">SHIFT VEHICLE PROFILE</p><h2 className="mt-2 text-2xl font-semibold">Choose your vehicle before going online.</h2><p className="mt-2 text-sm text-white/55">Capacity limits and visible map physics will follow this profile for this courier session.</p><div className="mt-6 grid gap-3 sm:grid-cols-3">{Object.entries(vehicleProfiles).map(([key, vehicle]) => <button key={key} onClick={() => protocol.selectVehicle(profile.id, key)} className="rounded-3xl border border-white/10 bg-white/[.04] p-5 text-left transition hover:-translate-y-1 hover:border-cyan/50 hover:bg-cyan/10"><span className="text-3xl">{vehicle.icon}</span><p className="mt-4 font-semibold">{vehicle.label}</p><p className="mt-2 text-xs text-cyan">{vehicle.speed} km/h</p><p className="mt-1 text-[10px] leading-4 text-white/45">{vehicle.weight} kg · {vehicle.volume} L capacity</p></button>)}</div></motion.div></motion.div>}{exceeded && <motion.div initial={{ opacity: 0, scale: .94 }} animate={{ opacity: 1, scale: 1 }} className="fixed inset-0 z-[1460] grid place-items-center bg-rose-950/70 p-5 backdrop-blur-md"><div className="w-full max-w-md rounded-[2rem] border border-rose-400/60 bg-[#260d19] p-7 shadow-[0_0_80px_rgba(255,0,85,.35)]"><ShieldAlert size={38} className="text-rose-300" /><h2 className="mt-5 text-2xl font-semibold">🚫 VEHICLE CAPACITY EXCEEDED</h2><p className="mt-3 text-sm leading-6 text-rose-100/75">Weight/Volume exceeds limits for the selected {limits.label} profile.</p></div></motion.div>}</AnimatePresence>
}

function LegacyJudgeDashboardDock({ protocol, onTrigger }) {
  const [decisionId, setDecisionId] = useState('PP-004')
  const [explanation, setExplanation] = useState(null)
  const continuousRiding = Math.max(0, protocol.simulatedMinutes - 14 * 60)
  const heatActive = protocol.simulatedMinutes >= 12 * 60 && protocol.simulatedMinutes <= 16 * 60 && continuousRiding > 90
  const mandatoryBreak = continuousRiding >= 240
  const shiftEndRisk = protocol.simulatedMinutes >= 22 * 60 + 15
  const triggerShock = (kind) => {
    protocol.setShock(kind)
    const mapped = { surge: 'SAN_PEDRO_SURGE', closure: 'ROAD_CLOSURE', rain: 'TORRENTIAL_RAIN', delay: 'SAN_PEDRO_CONGESTION' }
    onTrigger(mapped[kind])
  }
  const loadExplanation = async () => {
    try { setExplanation(await decisionApi.explain(decisionId)) } catch { setExplanation({ reason: 'No stored decision log for this order id yet.' }) }
  }
  return <aside className="protocol-dashboard-dock fixed bottom-5 right-5 z-[1200] w-[min(24rem,calc(100vw-2.5rem))]"><GlassCard className="max-h-[76vh] overflow-y-auto p-5"><div className="flex items-start justify-between"><div><p className="eyebrow">TIME MACHINE · 15×</p><h2 className="mt-1 text-lg font-semibold">{protocol.clock}</h2></div><button onClick={() => protocol.setPaused(!protocol.paused)} className="app-button px-3 py-2">{protocol.paused ? <Play size={15} /> : <Pause size={15} />}</button></div><div className="mt-3 flex flex-wrap gap-2">{['13:30', '15:41', '20:20', '22:05', '22:16'].map((time) => <button key={time} onClick={() => protocol.setSimulatedMinutes(time)} className="rounded-xl border border-white/10 px-2.5 py-1.5 text-[10px] text-white/65 hover:border-cyan/50">{time}</button>)}</div><div className="mt-5 border-t border-white/10 pt-4"><p className="text-[10px] font-semibold tracking-[.14em] text-white/45">INJECT SHOCK</p><div className="mt-2 grid grid-cols-2 gap-2">{['surge', 'closure', 'rain', 'delay'].map((kind) => <button key={kind} onClick={() => triggerShock(kind)} className="app-button px-2 py-2 text-xs capitalize">{kind}</button>)}</div></div><button onClick={() => protocol.toggleDegraded(!protocol.degraded)} className={`mt-4 flex w-full items-center justify-between rounded-2xl border p-3 text-left text-xs ${protocol.degraded ? 'border-amber-300/50 bg-amber-300/15 text-amber-100' : 'border-white/10 bg-white/[.04] text-white/65'}`}><span>Kill LLM Connection</span><span className="font-semibold">{protocol.degraded ? 'ON' : 'OFF'}</span></button>{protocol.degraded && <div className="mt-3 flex gap-2 rounded-2xl border border-amber-300/35 bg-amber-300/10 p-3 text-xs leading-5 text-amber-100"><AlertTriangle size={16} className="mt-0.5 shrink-0" />⚠️ DEGRADED MODE: Fast-path autonomous fallback active</div>}<div className="mt-5 border-t border-white/10 pt-4"><p className="text-[10px] font-semibold tracking-[.14em] text-white/45">DECISION LOGS</p><div className="mt-2 flex gap-2"><input value={decisionId} onChange={(event) => setDecisionId(event.target.value)} className="rumbo-input py-2 text-xs" aria-label="Decision order id" /><button onClick={loadExplanation} className="app-button px-3 py-2"><Gauge size={15} /></button></div>{explanation && <div className="mt-3 rounded-2xl border border-white/10 bg-black/20 p-3 text-xs leading-5 text-white/60"><b className="text-white">{explanation.decision || 'LOG'}</b> · {explanation.reason}</div>}</div></GlassCard><AnimatePresence>{(heatActive || mandatoryBreak || shiftEndRisk) && <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mt-3 rounded-2xl border border-rose-400/40 bg-rose-500/15 p-4 text-xs leading-5 text-rose-100">{mandatoryBreak ? '🛑 MANDATORY BREAK — 4 continuous hours reached.' : heatActive ? '🔥 HEAT RULE ACTIVE — Cooling period required.' : '⌛ SHIFT END INFEASIBLE — Verify ETA before accepting.'}</motion.div>}</AnimatePresence></aside>
}

/** Compact by default so it never covers the map, AI verdict, or header actions. */
export function JudgeDashboardDock({ protocol, drivers = [] }) {
  const [open, setOpen] = useState(false)
  const [decisionId, setDecisionId] = useState('PP-004')
  const [explanation, setExplanation] = useState(null)
  const [delayDriverId, setDelayDriverId] = useState('')
  const [notice, setNotice] = useState('')
  const continuousRiding = Math.max(0, protocol.simulatedMinutes - 14 * 60)
  const heatActive = protocol.simulatedMinutes >= 12 * 60 && protocol.simulatedMinutes <= 16 * 60 && continuousRiding > 90
  const mandatoryBreak = continuousRiding >= 240
  const shiftEndRisk = protocol.simulatedMinutes >= 22 * 60 + 15
  const loadExplanation = async () => {
    try { setExplanation(await decisionApi.explain(decisionId)) } catch { setExplanation({ reason: 'No stored decision log for this order id yet.' }) }
  }
  const setTime = async (event) => {
    try { await protocol.setSimulatedMinutes(event.target.value) } catch { setNotice('The Pi could not update the shared clock.') }
  }
  const injectShock = async (kind) => {
    try {
      if (kind === 'closure') {
        protocol.setClosurePinMode(true)
        setNotice('Click an avenue on the map to pin the road closure.')
      } else if (kind === 'delay') {
        if (!delayDriverId) return setNotice('Select an active courier before applying a delay.')
        await protocol.delayDriver(delayDriverId, 15)
        setNotice('The selected courier is DECAY / DELAYED for 15 simulated minutes.')
      } else {
        await protocol.triggerShock(kind)
        setNotice(`${kind[0].toUpperCase() + kind.slice(1)} was synchronized from the Pi to every connected laptop.`)
      }
    } catch (error) { setNotice(error.message || 'The Pi could not apply this control.') }
  }
  return <aside className="protocol-dashboard-dock fixed bottom-5 right-5 z-[55] w-[min(22rem,calc(100vw-2.5rem))]">
    {!open && <button onClick={() => setOpen(true)} className="glass flex w-full items-center justify-between rounded-2xl px-4 py-3 text-left text-xs shadow-2xl"><span><b className="block text-cyan">TIME MACHINE · {protocol.clock}</b><span className="mt-1 block text-white/45">Shared Pi controls</span></span><Gauge size={18} className="text-cyan" /></button>}
    <AnimatePresence>{open && <motion.div initial={{ opacity: 0, y: 12, scale: .98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 12, scale: .98 }} className="max-h-[68vh] overflow-y-auto rounded-[1.5rem] border border-white/10 bg-slate-900/90 p-5 shadow-2xl backdrop-blur-md"><div className="flex items-start justify-between"><div><p className="eyebrow">TIME MACHINE · 15×</p><h2 className="mt-1 text-lg font-semibold">{protocol.clock}</h2></div><div className="flex gap-2"><button onClick={() => protocol.setPaused(!protocol.paused)} className="app-button px-3 py-2">{protocol.paused ? <Play size={15} /> : <Pause size={15} />}</button><button onClick={() => setOpen(false)} className="app-button px-3 py-2">×</button></div></div><label className="mt-4 block"><span className="mb-1 block text-[10px] tracking-[.14em] text-white/45">SHARED SIMULATION TIME</span><select value={protocol.clock} onChange={setTime} className="rumbo-input py-2 text-sm"><option>13:30</option><option>15:41</option><option>20:20</option><option>22:05</option><option>22:16</option></select></label><div className="mt-5 border-t border-white/10 pt-4"><p className="text-[10px] font-semibold tracking-[.14em] text-white/45">INJECT SHOCK</p><div className="mt-2 grid grid-cols-2 gap-2"><button onClick={() => injectShock('surge')} className="app-button px-2 py-2 text-xs">Surge</button><button onClick={() => injectShock('closure')} className={`app-button px-2 py-2 text-xs ${protocol.closurePinMode ? 'border-rose-300/50 bg-rose-500/15 text-rose-100' : ''}`}>Closure</button><button onClick={() => injectShock('rain')} className="app-button px-2 py-2 text-xs">Rain</button><button onClick={() => injectShock('delay')} className="app-button px-2 py-2 text-xs">Delay</button></div><select value={delayDriverId} onChange={(event) => setDelayDriverId(event.target.value)} className="rumbo-input mt-2 py-2 text-xs"><option value="">Select courier for delay</option>{drivers.filter((driver) => driver.online).map((driver) => <option key={driver.id} value={driver.id}>{driver.name}</option>)}</select></div><button onClick={() => protocol.toggleDegraded(!protocol.degraded)} className={`mt-4 flex w-full items-center justify-between rounded-2xl border p-3 text-left text-xs ${protocol.degraded ? 'border-amber-300/50 bg-amber-300/15 text-amber-100' : 'border-white/10 bg-white/[.04] text-white/65'}`}><span>Kill LLM Connection</span><span className="font-semibold">{protocol.degraded ? 'ON' : 'OFF'}</span></button>{protocol.degraded && <div className="mt-3 flex gap-2 rounded-2xl border border-amber-300/35 bg-amber-300/10 p-3 text-xs leading-5 text-amber-100"><AlertTriangle size={16} className="mt-0.5 shrink-0" />⚠️ DEGRADED MODE: Fast-path autonomous fallback active</div>}<div className="mt-5 border-t border-white/10 pt-4"><p className="text-[10px] font-semibold tracking-[.14em] text-white/45">DECISION LOGS</p><div className="mt-2 flex gap-2"><input value={decisionId} onChange={(event) => setDecisionId(event.target.value)} className="rumbo-input py-2 text-xs" aria-label="Decision order id" /><button onClick={loadExplanation} className="app-button px-3 py-2"><Gauge size={15} /></button></div>{explanation && <div className="mt-3 max-h-32 overflow-y-auto rounded-2xl border border-white/10 bg-black/20 p-3 text-xs leading-5 text-white/60"><b className="text-white">{explanation.decision || 'LOG'}</b> · {explanation.reason}</div>}</div>{notice && <p className="mt-4 rounded-xl border border-cyan/20 bg-cyan/10 p-3 text-xs leading-5 text-cyan">{notice}</p>}</motion.div>}</AnimatePresence><AnimatePresence>{(heatActive || mandatoryBreak || shiftEndRisk) && <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mt-3 rounded-2xl border border-rose-400/40 bg-rose-500/15 p-4 text-xs leading-5 text-rose-100">{mandatoryBreak ? '🛑 MANDATORY BREAK — 4 continuous hours reached.' : heatActive ? '🔥 HEAT RULE ACTIVE — Cooling period required.' : '⌛ SHIFT END INFEASIBLE — Verify ETA before accepting.'}</motion.div>}</AnimatePresence></aside>
}
