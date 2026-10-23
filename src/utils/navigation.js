/** The interview session/evaluation screens hide navigation so the candidate stays focused. */
export const isFocusRoute = (pathname) => pathname === '/interview/session' || pathname === '/interview/evaluation';

/** Maps the current path to the nav item that should look active. */
export function getActiveNavPath(pathname) {
  if (pathname.startsWith('/interview')) return '/cv-upload';
  if (pathname === '/results') return '/history';
  if (pathname.startsWith('/profile')) return '/profile';
  if (pathname.startsWith('/plan')) return '/performance';
  return pathname;
}
