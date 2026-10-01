import { motion } from 'framer-motion';
import { ease, fadeUp, staggerContainer, viewportOnce } from '../animations/variants';

/** Fades/slides its content in when scrolled into view. */
export function Reveal({ as = 'div', delay = 0, y = 18, className, children, ...rest }) {
  const Comp = motion[as] ?? motion.div;
  return (
    <Comp
      className={className}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={viewportOnce}
      transition={{ duration: 0.55, ease, delay }}
      {...rest}
    >
      {children}
    </Comp>
  );
}

/** Container that reveals its motion children one after another (on mount, or on scroll with `inView`). */
export function Stagger({ as = 'div', gap = 0.08, delay = 0, inView = false, className, children, ...rest }) {
  const Comp = motion[as] ?? motion.div;
  const trigger = inView ? { whileInView: 'show', viewport: viewportOnce } : { animate: 'show' };
  return (
    <Comp className={className} variants={staggerContainer(gap, delay)} initial="hidden" {...trigger} {...rest}>
      {children}
    </Comp>
  );
}

/** Nested list that inherits its trigger from the closest <Stagger>/<Card> ancestor. */
export function StaggerList({ as = 'ul', gap = 0.08, delay = 0.15, className, children, ...rest }) {
  const Comp = motion[as] ?? motion.ul;
  return <Comp className={className} variants={staggerContainer(gap, delay)} {...rest}>{children}</Comp>;
}

export function StaggerItem({ as = 'div', className, children, ...rest }) {
  const Comp = motion[as] ?? motion.div;
  return <Comp className={className} variants={fadeUp} {...rest}>{children}</Comp>;
}
