import { useEffect, useRef, useState } from 'react'

function interpolateHeading(from, to, progress) {
  const difference = ((to - from + 540) % 360) - 180
  return (from + difference * progress + 360) % 360
}

/** Smooth a 2 Hz Raspberry telemetry stream into display-frame-rate motion. */
export function useInterpolatedTelemetry(telemetry) {
  const [display, setDisplay] = useState(telemetry || null)
  const current = useRef(telemetry || null)
  useEffect(() => {
    if (!telemetry?.position) return undefined
    const from = current.current?.position || telemetry.position
    const fromBearing = current.current?.bearing ?? telemetry.bearing ?? 0
    const startedAt = performance.now()
    let frame = 0
    const animate = (now) => {
      const progress = Math.min(1, (now - startedAt) / 470)
      const position = [
        from[0] + (telemetry.position[0] - from[0]) * progress,
        from[1] + (telemetry.position[1] - from[1]) * progress,
      ]
      const next = { ...telemetry, position, bearing: interpolateHeading(fromBearing, telemetry.bearing ?? fromBearing, progress) }
      current.current = next
      setDisplay(next)
      if (progress < 1) frame = requestAnimationFrame(animate)
    }
    frame = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(frame)
  }, [telemetry?.timestamp, telemetry?.position?.[0], telemetry?.position?.[1], telemetry?.bearing])
  return display || telemetry || null
}
