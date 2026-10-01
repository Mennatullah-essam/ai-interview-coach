import { motion } from 'framer-motion';
import { fadeUp } from '../animations/variants';

/** Clickable row that is also reachable and operable with the keyboard. */
export default function PressableRow({ onActivate, label, className, children, ...rest }) {
  const onKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onActivate();
    }
  };
  return (
    <motion.div role="button" tabIndex={0} aria-label={label} className={className} onClick={onActivate} onKeyDown={onKeyDown} variants={fadeUp} whileTap={{ scale: 0.995 }} {...rest}>
      {children}
    </motion.div>
  );
}
