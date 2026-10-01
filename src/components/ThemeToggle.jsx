import { AnimatePresence, motion } from 'framer-motion';
import Button from './Button';
import { useTheme } from '../hooks/useTheme';

export default function ThemeToggle() {
  const { dark, toggle } = useTheme();
  return (
    <Button className="icon" onClick={toggle} title="Toggle dark mode" aria-label="Toggle dark mode" aria-pressed={dark}>
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={dark ? 'sun' : 'moon'}
          style={{ display: 'inline-block' }}
          initial={{ rotate: -90, opacity: 0, scale: 0.6 }}
          animate={{ rotate: 0, opacity: 1, scale: 1 }}
          exit={{ rotate: 90, opacity: 0, scale: 0.6 }}
          transition={{ duration: 0.18 }}
        >
          {dark ? '☀️' : '🌙'}
        </motion.span>
      </AnimatePresence>
    </Button>
  );
}
