import { Navigate } from 'react-router-dom';
import { useIsPresent } from 'framer-motion';
import { useApp } from '../hooks/useApp';
import { useInterview } from '../hooks/useInterview';

/**
 * Redirects when `allow` is false. Ignored while the page is animating out, because
 * state is intentionally changed right before navigating away.
 */
function Guard({ allow, to, children }) {
  const isPresent = useIsPresent();
  if (!allow && isPresent) return <Navigate to={to} replace />;
  return children;
}

/** The question screen needs an active session whose current question is still unanswered. */
export function SessionGuard({ children }) {
  const { session, currentEval } = useInterview();
  return <Guard allow={Boolean(session) && !currentEval} to={session ? '/interview/evaluation' : '/interview/setup'}>{children}</Guard>;
}

/** The evaluation screen needs an evaluated answer. */
export function EvaluationGuard({ children }) {
  const { session, currentEval } = useInterview();
  return <Guard allow={Boolean(session) && Boolean(currentEval)} to={session ? '/interview/session' : '/interview/setup'}>{children}</Guard>;
}

/** Results are only reachable after an interview was finished or opened from history. */
export function ResultsGuard({ children }) {
  const { resultsStatus } = useApp();
  return <Guard allow={resultsStatus !== 'idle'} to="/history">{children}</Guard>;
}
