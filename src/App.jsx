import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { AnimatePresence, MotionConfig, motion } from 'framer-motion';
import { ThemeProvider } from './context/ThemeContext';
import { ToastProvider } from './context/ToastContext';
import { AuthProvider } from './context/AuthContext';
import { AppProvider } from './context/AppContext';
import { InterviewProvider } from './context/InterviewContext';
import AppLayout from './components/AppLayout';
import { EvaluationGuard, RedirectIfAuthenticated, RequireAuth, ResultsGuard, SessionGuard } from './components/RouteGuards';
import { useAuth } from './hooks/useAuth';
import Landing from './pages/Landing';
import AuthPage from './pages/AuthPage';
import Dashboard from './pages/Dashboard';
import CVUpload from './pages/CVUpload';
import InterviewSetup from './pages/InterviewSetup';
import InterviewSession from './pages/InterviewSession';
import Evaluation from './pages/Evaluation';
import Results from './pages/Results';
import InterviewHistory from './pages/InterviewHistory';
import Performance from './pages/Performance';
import Profile from './pages/Profile';
import ProfileReview from './pages/ProfileReview';
import ImprovementPlan from './pages/ImprovementPlan';

const sectionOf = (pathname) => {
  if (pathname === '/') return 'landing';
  if (pathname === '/login' || pathname === '/signup') return 'auth';
  return 'app';
};

/** Cross-fades between the landing page, the auth pages and the signed-in app shell. */
function AnimatedRoutes() {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait" onExitComplete={() => window.scrollTo(0, 0)}>
      {/* Opacity only: a transform here would break position: fixed descendants. */}
      <motion.div key={sectionOf(location.pathname)} initial={{ opacity: 0 }} animate={{ opacity: 1, transition: { duration: 0.3 } }} exit={{ opacity: 0, transition: { duration: 0.15 } }}>
        <Routes location={location}>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<RedirectIfAuthenticated><AuthPage mode="login" /></RedirectIfAuthenticated>} />
          <Route path="/signup" element={<RedirectIfAuthenticated><AuthPage mode="signup" /></RedirectIfAuthenticated>} />
          <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/cv-upload" element={<CVUpload />} />
            <Route path="/interview/setup" element={<InterviewSetup />} />
            <Route path="/interview/session" element={<SessionGuard><InterviewSession /></SessionGuard>} />
            <Route path="/interview/evaluation" element={<EvaluationGuard><Evaluation /></EvaluationGuard>} />
            <Route path="/results" element={<ResultsGuard><Results /></ResultsGuard>} />
            <Route path="/history" element={<InterviewHistory />} />
            <Route path="/performance" element={<Performance />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/profile/review" element={<ProfileReview />} />
            <Route path="/plan" element={<ImprovementPlan />} />
            <Route path="/plan/:interviewId" element={<ImprovementPlan />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  );
}

/** Per-user state. Keyed by the user id so nothing leaks between accounts after sign-out. */
function UserScopedProviders({ children }) {
  const { user } = useAuth();
  return (
    <AppProvider key={user?.id ?? 'anonymous'}>
      <InterviewProvider>{children}</InterviewProvider>
    </AppProvider>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <AuthProvider>
          <UserScopedProviders>
            <MotionConfig reducedMotion="user">
              <AnimatedRoutes />
            </MotionConfig>
          </UserScopedProviders>
        </AuthProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}
