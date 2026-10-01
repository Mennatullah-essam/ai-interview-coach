import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { THINKING_MESSAGES } from '../data/constants';

/** Spinner + bouncing dots + rotating status line shown while the AI evaluates an answer. */
export default function ThinkingIndicator({ title = 'AI is analyzing your answer…' }) {
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI((x) => (x + 1) % THINKING_MESSAGES.length), 1600);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="thinking" role="status">
      <div className="spin" aria-hidden="true" />
      <p className="thinking-title">{title}</p>
      <div className="dots" aria-hidden="true"><span /><span /><span /></div>
      <div aria-hidden="true" style={{ minHeight: '1.6em' }}>
        <AnimatePresence mode="wait" initial={false}>
          <motion.p key={i} className="mut" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.2 }}>
            {THINKING_MESSAGES[i]}
          </motion.p>
        </AnimatePresence>
      </div>
    </div>
  );
}
