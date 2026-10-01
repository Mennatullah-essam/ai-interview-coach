import { motion } from 'framer-motion';

const pillSpring = { type: 'spring', stiffness: 500, damping: 38 };

/**
 * Static badge by default. With `onClick` it becomes a toggle button; pass `layoutId`
 * so the selected highlight glides between chips of the same group.
 */
export default function Chip({ tone, size, selected = false, onClick, layoutId, className = '', children, ...rest }) {
  if (!onClick) {
    const cls = ['chip', tone, size, selected && 'sel', className].filter(Boolean).join(' ');
    return <span className={cls} {...rest}>{children}</span>;
  }
  const cls = ['chip', 'chip-pick', tone, size, selected && 'is-active', className].filter(Boolean).join(' ');
  return (
    <motion.button type="button" className={cls} onClick={onClick} aria-pressed={selected} whileTap={{ scale: 0.95 }} {...rest}>
      {selected && layoutId && <motion.span layoutId={layoutId} className="chip-active" transition={pillSpring} />}
      <span>{children}</span>
    </motion.button>
  );
}
