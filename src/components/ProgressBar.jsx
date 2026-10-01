import { useRef } from 'react';
import { motion, useInView, useReducedMotion } from 'framer-motion';
import { ease } from '../animations/variants';

/** Animated progress bar. Fills when scrolled into view and eases whenever `value` changes. */
export default function ProgressBar({ value, label, ariaLabel, fast = false, delay = 0, className }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '0px 0px -40px 0px' });
  const reduce = useReducedMotion();
  const duration = reduce ? 0 : fast ? 0.25 : 0.9;

  return (
    <div className={className}>
      {label && (
        <div className="row sp bar-head">
          <span>{label}</span>
          <b>{value}%</b>
        </div>
      )}
      <div ref={ref} className="bar" role="progressbar" aria-label={label ?? ariaLabel} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(value)}>
        <motion.div initial={{ width: 0 }} animate={{ width: `${inView ? value : 0}%` }} transition={{ duration, delay: reduce ? 0 : delay, ease }} />
      </div>
    </div>
  );
}
