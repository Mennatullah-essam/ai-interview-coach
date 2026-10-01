import { forwardRef } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';

const MotionLink = motion.create(Link);
const spring = { type: 'spring', stiffness: 500, damping: 30 };

/** Button or router link (when `to` is set) styled with the shared .btn classes. */
const Button = forwardRef(function Button({ variant = 'default', size, to, className, children, ...rest }, ref) {
  const cls = ['btn', variant === 'primary' && 'p', size, className].filter(Boolean).join(' ');
  const gestures = rest.disabled
    ? {}
    : { whileHover: { y: -1 }, whileTap: { scale: 0.97 }, transition: spring };

  if (to) {
    return <MotionLink ref={ref} to={to} className={cls} {...gestures} {...rest}>{children}</MotionLink>;
  }
  return <motion.button ref={ref} type="button" className={cls} {...gestures} {...rest}>{children}</motion.button>;
});

export default Button;
