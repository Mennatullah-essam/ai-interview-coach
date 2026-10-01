import { motion } from 'framer-motion';
import { fadeUp } from '../animations/variants';

/**
 * Card surface. Inside a <Stagger> it reveals in sequence; set `enter` to animate on mount by itself.
 */
export default function Card({ as = 'div', hover = false, enter = false, tinted = false, className = '', children, ...rest }) {
  const Comp = motion[as] ?? motion.div;
  const cls = ['card', hover && 'h', tinted && 'tinted', className].filter(Boolean).join(' ');
  return (
    <Comp
      className={cls}
      variants={fadeUp}
      {...(enter ? { initial: 'hidden', animate: 'show' } : {})}
      whileHover={hover ? { y: -3 } : undefined}
      {...rest}
    >
      {children}
    </Comp>
  );
}
