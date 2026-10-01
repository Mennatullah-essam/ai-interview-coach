import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { AnimatePresence, MotionConfig, motion } from 'framer-motion';
import { ThemeProvider } from './context/ThemeContext';
import { ToastProvider } from './context/ToastContext';
import { AppProvider } from './context/AppContext';
import { InterviewProvider } from './context/InterviewContext';
import AppLayout from './components/AppLayout';
import { EvaluationGuard, ResultsGuard, SessionGuard } from './components/RouteGuards';
import Landing from './pages/Landing';
import Dashboard from './pages/Dashboard';
import CVUpload from './pages/CVUpload';
import InterviewSetup from './pages/InterviewSetup';
import InterviewSession from './pages/InterviewSession';
import Evaluation from './pages/Evaluation';
import Results from './pages/Results';
import InterviewHistory from './pages/InterviewHistory';
import Performance from './pages/Performance';
import Profile from './pages/Profile';

/** Cross-fades between the marketing landing page and the signed-in app shell. */
function AnimatedRoutes() {
  const location = useLocation();
  const section = location.pathname === '/' ? 'landing' : 'app';

  return (
    <AnimatePresence mode="wait" onExitComplete={() => window.scrollTo(0, 0)}>
      {/* Opacity only: a transform here would break position: fixed descendants. */}
      <motion.div key={section} initial={{ opacity: 0 }} animate={{ opacity: 1, transition: { duration: 0.3 } }} exit={{ opacity: 0, transition: { duration: 0.15 } }}>
        <Routes location={location}>
          <Route path="/" element={<Landing />} />
          <Route element={<AppLayout />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/cv-upload" element={<CVUpload />} />
            <Route path="/interview/setup" element={<InterviewSetup />} />
            <Route path="/interview/session" element={<SessionGuard><InterviewSession /></SessionGuard>} />
            <Route path="/interview/evaluation" element={<EvaluationGuard><Evaluation /></EvaluationGuard>} />
            <Route path="/results" element={<ResultsGuard><Results /></ResultsGuard>} />
            <Route path="/history" element={<InterviewHistory />} />
            <Route path="/performance" element={<Performance />} />
            <Route path="/profile" element={<Profile />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <AppProvider>
          <InterviewProvider>
            <MotionConfig reducedMotion="user">
              <AnimatedRoutes />
            </MotionConfig>
          </InterviewProvider>
        </AppProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}
