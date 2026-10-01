import { AnimatePresence, motion } from 'framer-motion';

/** Bold value that cross-fades when it changes. */
export default function AnimatedValue({ value }) {
  return (
    <span style={{ display: 'inline-block', overflow: 'hidden' }}>
      <AnimatePresence mode="wait" initial={false}>
        <motion.b
          key={String(value)}
          style={{ display: 'inline-block' }}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.15 }}
        >
          {value}
        </motion.b>
      </AnimatePresence>
    </span>
  );
}
