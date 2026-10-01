import { useEffect, useState } from 'react';
import { animate, useReducedMotion } from 'framer-motion';

/** Animates an integer from 0 to `target`. */
export function useCountUp(target, { duration = 1.1, delay = 0 } = {}) {
  const reduce = useReducedMotion();
  const [value, setValue] = useState(reduce ? target : 0);

  useEffect(() => {
    if (reduce) { setValue(target); return undefined; }
    const controls = animate(0, target, { duration, delay, ease: 'easeOut', onUpdate: (v) => setValue(Math.round(v)) });
    return () => controls.stop();
  }, [target, duration, delay, reduce]);

  return value;
}
