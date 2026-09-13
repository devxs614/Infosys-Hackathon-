export function RumboBrand({ className = '', subtitle = 'EDGE LOGISTICS OS' }) {
  return <span className={`inline-flex min-w-0 items-center gap-2.5 ${className}`}>
    <img src="/rumbo-logo.png" alt="Rumbo" className="h-9 w-auto rounded-lg object-contain shadow-[0_0_22px_rgba(74,180,255,.22)]" />
    {subtitle && <span className="min-w-0"><b className="block truncate text-sm tracking-tight">Rumbo</b><small className="block truncate text-[9px] tracking-[.18em] text-white/40">{subtitle}</small></span>}
  </span>
}
