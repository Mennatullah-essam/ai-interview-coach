import { useEffect } from 'react';
import { motion } from 'framer-motion';
import { ease } from '../animations/variants';

/** Wraps a routed page: fade/slide in on enter, quick fade out on exit. Also resets scroll and moves focus to <main>. */
export default function PageTransition({ children }) {
  useEffect(() => {
    window.scrollTo(0, 0);
    document.getElementById('main')?.focus({ preventScroll: true });
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0, transition: { duration: 0.4, ease } }}
      exit={{ opacity: 0, y: -8, transition: { duration: 0.16 } }}
    >
      {children}
    </motion.div>
  );
}
