import { Link, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import { NAV_ITEMS } from '../data/constants';
import { getActiveNavPath } from '../utils/navigation';

/** Bottom navigation shown on small screens (the top links are hidden there). */
export default function MobileTabBar() {
  const { pathname } = useLocation();
  const active = getActiveNavPath(pathname);
  return (
    <motion.nav
      className="tabs"
      aria-label="Primary mobile"
      initial={{ y: 70, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ type: 'spring', stiffness: 260, damping: 28, delay: 0.1 }}
    >
      {NAV_ITEMS.map((item) => (
        <Link key={item.path} to={item.path} className={`tab-link${active === item.path ? ' on' : ''}`} aria-current={active === item.path ? 'page' : undefined}>
          {active === item.path && <motion.span layoutId="tab-pill" className="tab-pill" transition={{ type: 'spring', stiffness: 500, damping: 38 }} />}
          <b aria-hidden="true">{item.icon}</b>
          {item.short}
        </Link>
      ))}
    </motion.nav>
  );
}
