import { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import Logo from './Logo';
import Button from './Button';
import ThemeToggle from './ThemeToggle';
import { NAV_ITEMS } from '../data/constants';
import { useApp } from '../hooks/useApp';
import { getActiveNavPath, isFocusRoute } from '../utils/navigation';
import { getFirstName, getInitials } from '../utils/format';

const pillSpring = { type: 'spring', stiffness: 500, damping: 38 };

/** Sticky top bar. `variant="landing"` shows the marketing header; otherwise the signed-in app navigation. */
export default function Navbar({ variant = 'app' }) {
  const { user } = useApp();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const avatar = useRef(null);
  const menu = useRef(null);
  const focusMode = isFocusRoute(pathname);
  const active = getActiveNavPath(pathname);

  useEffect(() => { setMenuOpen(false); }, [pathname]);

  useEffect(() => {
    if (!menuOpen) return undefined;
    const onPointer = (e) => {
      if (!menu.current?.contains(e.target) && !avatar.current?.contains(e.target)) setMenuOpen(false);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') { setMenuOpen(false); avatar.current?.focus(); }
    };
    document.addEventListener('mousedown', onPointer);
    document.addEventListener('keydown', onKey);
    menu.current?.querySelector('button')?.focus();
    return () => {
      document.removeEventListener('mousedown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [menuOpen]);

  const go = (path) => { setMenuOpen(false); navigate(path); };

  if (variant === 'landing') {
    return (
      <motion.header className="top" initial={{ opacity: 0, y: -16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
        <div className="in">
          <Logo />
          <div style={{ flex: 1 }} />
          <ThemeToggle />
          <Button to="/dashboard">Sign in as {getFirstName(user.name)}</Button>
        </div>
      </motion.header>
    );
  }

  return (
    <header className="top">
      <div className="in">
        <Logo to={focusMode ? undefined : '/'} />
        {!focusMode && (
          <nav className="nav-links" aria-label="Primary">
            {NAV_ITEMS.map((item) => (
              <Link key={item.path} to={item.path} className={`nav-link${active === item.path ? ' on' : ''}`} aria-current={active === item.path ? 'page' : undefined}>
                {active === item.path && <motion.span layoutId="nav-pill" className="nav-pill" transition={pillSpring} />}
                {item.label}
              </Link>
            ))}
          </nav>
        )}
        <div style={{ flex: 1 }} />
        <ThemeToggle />
        {!focusMode && (
          <motion.button
            ref={avatar}
            type="button"
            className="av"
            aria-label="Account menu"
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((o) => !o)}
            whileHover={{ scale: 1.06 }}
            whileTap={{ scale: 0.94 }}
          >
            {getInitials(user.name)}
          </motion.button>
        )}
      </div>
      <AnimatePresence>
        {menuOpen && (
          <motion.div
            ref={menu}
            className="menu"
            role="menu"
            initial={{ opacity: 0, scale: 0.95, y: -6 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: -4 }}
            transition={{ duration: 0.15 }}
          >
            <button type="button" role="menuitem" onClick={() => go('/profile')}>👤 Profile &amp; settings</button>
            <button type="button" role="menuitem" onClick={() => go('/')}>↩ Sign out</button>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
