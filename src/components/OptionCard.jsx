import { motion } from 'framer-motion';

/** Large selectable option (e.g. interview type). The selection ring animates between options. */
export default function OptionCard({ title, description, selected, onClick, layoutId }) {
  return (
    <motion.button type="button" className={`opt${selected ? ' sel' : ''}`} onClick={onClick} aria-pressed={selected} whileTap={{ scale: 0.98 }}>
      {selected && <motion.span layoutId={layoutId} className="opt-ring" transition={{ type: 'spring', stiffness: 450, damping: 36 }} />}
      <b>{title}</b>
      <div className="mut">{description}</div>
    </motion.button>
  );
}
