import { useCountUp } from '../hooks/useCountUp';

/** Number that counts up when it appears; screen readers get the final value immediately. */
export default function CountUp({ value, suffix = '', delay = 0 }) {
  const shown = useCountUp(value, { delay });
  return (
    <>
      <span aria-hidden="true">{shown}{suffix}</span>
      <span className="sr-only">{value}{suffix}</span>
    </>
  );
}
