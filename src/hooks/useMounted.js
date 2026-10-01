import { useEffect, useRef } from 'react';

/** Ref that is true while the component is mounted; guards navigation after async work. */
export function useMounted() {
  const mounted = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  return mounted;
}
