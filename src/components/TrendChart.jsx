import { useRef } from 'react';
import { motion, useInView, useReducedMotion } from 'framer-motion';
import { ease } from '../animations/variants';

const BAR_SCALE = 1.3; // px of height per score point

/** Simple animated bar chart; bars grow upward in sequence when scrolled into view. */
export default function TrendChart({ data }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '0px 0px -40px 0px' });
  const reduce = useReducedMotion();
  const summary = data.map((d) => `${d.label}: ${d.value}`).join(', ');

  return (
    <div ref={ref} className="trend" role="img" aria-label={`Score trend. ${summary}`}>
      {data.map((d, i) => (
        <div key={d.id} aria-hidden="true">
          <motion.span
            initial={{ height: 0 }}
            animate={{ height: inView ? d.value * BAR_SCALE : 0 }}
            transition={{ duration: reduce ? 0 : 0.8, delay: reduce ? 0 : i * 0.12, ease }}
          />
          <b>{d.value}</b>
          <div className="mut">{d.label}</div>
        </div>
      ))}
    </div>
  );
}
