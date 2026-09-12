import { motion } from 'framer-motion'

export function GlassCard({ children, className = '', delay = 0, ...props }) {
  return <motion.section initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .5, delay }} className={`glass rounded-3xl ${className}`} {...props}>{children}</motion.section>
}
