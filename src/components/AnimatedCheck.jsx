import { motion } from 'framer-motion';

/** Check mark that draws itself. */
export default function AnimatedCheck({ size = 14, delay = 0.2 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <motion.path d="M4 12.5l5 5L20 6.5" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.4, delay, ease: 'easeOut' }} />
    </svg>
  );
}
