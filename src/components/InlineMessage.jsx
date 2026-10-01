import { AnimatePresence, motion } from 'framer-motion';

/** Animated validation/error message. `variant="box"` renders the larger alert style. */
export default function InlineMessage({ message, variant = 'field', id }) {
  return (
    <AnimatePresence initial={false}>
      {message && (
        <motion.div
          key={message}
          id={id}
          role="alert"
          className={variant === 'box' ? 'errbox' : 'err'}
          initial={{ opacity: 0, y: -6, height: 0 }}
          animate={{ opacity: 1, y: 0, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          transition={{ duration: 0.2 }}
          style={{ overflow: 'hidden' }}
        >
          {variant === 'box' ? `⚠️ ${message}` : message}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
