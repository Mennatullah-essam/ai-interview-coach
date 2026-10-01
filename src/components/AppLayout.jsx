import { useRef } from 'react';
import { useLocation, useOutlet } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import Navbar from './Navbar';
import MobileTabBar from './MobileTabBar';
import PageTransition from './PageTransition';
import { useInterview } from '../hooks/useInterview';
import { isFocusRoute } from '../utils/navigation';

/** Shell for every signed-in screen: top bar, animated page area and the mobile tab bar. */
export default function AppLayout() {
  const { pathname } = useLocation();
  const outlet = useOutlet();
  const { reset } = useInterview();
  const pathRef = useRef(pathname);
  pathRef.current = pathname;

  // Clear interview progress only after the leaving page has finished animating out,
  // so it never re-renders with half-cleared state while fading.
  const handleExitComplete = () => {
    if (!pathRef.current.startsWith('/interview/')) reset();
  };

  return (
    <>
      <a href="#main" className="skip-link">Skip to content</a>
      <Navbar />
      <main id="main" tabIndex={-1}>
        <AnimatePresence mode="wait" onExitComplete={handleExitComplete}>
          <PageTransition key={pathname}>{outlet}</PageTransition>
        </AnimatePresence>
      </main>
      {!isFocusRoute(pathname) && <MobileTabBar />}
    </>
  );
}
