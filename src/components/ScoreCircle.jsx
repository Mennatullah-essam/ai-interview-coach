import { useEffect, useId } from 'react';
import { animate, motion, useMotionValue, useReducedMotion, useTransform } from 'framer-motion';
import { ease } from '../animations/variants';

/** Circular score that counts and fills from 0 to `value`. */
export default function ScoreCircle({ value, size = 130, label = '/ 100', ariaLabel = 'Score', delay = 0.2 }) {
  const gradId = `rg${useId().replace(/:/g, '')}`;
  const reduce = useReducedMotion();
  const stroke = 9;
  const r = size / 2 - stroke;
  const c = 2 * Math.PI * r;
  const progress = useMotionValue(reduce ? value : 0);
  const offset = useTransform(progress, (v) => c * (1 - v / 100));
  const shown = useTransform(progress, (v) => Math.round(v));

  useEffect(() => {
    if (reduce) { progress.set(value); return undefined; }
    const controls = animate(progress, value, { duration: 1.3, delay, ease });
    return () => controls.stop();
  }, [value, reduce, delay, progress]);

  return (
    <div className="ring" style={{ width: size, height: size }} role="img" aria-label={`${ariaLabel}: ${value} out of 100`}>
      <svg width={size} height={size} aria-hidden="true">
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#4f46e5" />
            <stop offset="1" stopColor="#7c3aed" />
          </linearGradient>
        </defs>
        <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" style={{ stroke: 'var(--track)' }} strokeWidth={stroke} />
          <motion.circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={`url(#${gradId})`} strokeWidth={stroke} strokeLinecap="round" strokeDasharray={c} style={{ strokeDashoffset: offset }} />
        </g>
      </svg>
      <div className="rv" aria-hidden="true">
        <motion.b>{shown}</motion.b>
        <small>{label}</small>
      </div>
    </div>
  );
}
