import { createContext, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import api from '../services/api';
import { useAuth } from '../hooks/useAuth';
import { DEFAULT_CONFIG } from '../data/constants';

export const AppContext = createContext(null);

/**
 * Holds the signed-in user's CV, interview configuration, history, skills and
 * the currently viewed results. Everything is loaded from the backend; this
 * provider is re-created when the signed-in user changes.
 */
export function AppProvider({ children }) {
  const { user, setUser, status } = useAuth();
  const [cvFile, setCvFile] = useState(null);
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  const [history, setHistory] = useState(null);
  const [skills, setSkills] = useState(null);
  const [loadError, setLoadError] = useState('');
  const [results, setResults] = useState(null);
  const [resultsStatus, setResultsStatus] = useState('idle'); // idle | loading | ready | error
  const resultsRequest = useRef(0);

  const loadDashboardData = useCallback(() => {
    setLoadError('');
    api.getInterviewHistory().then(setHistory).catch((e) => { console.error(e); setHistory([]); setLoadError('Could not load your interview history.'); });
    api.getSkills().then(setSkills).catch((e) => { console.error(e); setSkills({}); });
  }, []);

  useEffect(() => {
    if (status !== 'authenticated') return;
    loadDashboardData();
    // Restore the most recent CV after a page reload.
    api.getLatestCV().then((cv) => setCvFile((current) => current ?? cv)).catch((e) => console.error(e));
  }, [status, loadDashboardData]);

  const openResults = useCallback(async (meta) => {
    const request = ++resultsRequest.current;
    setResults(null);
    setResultsStatus('loading');
    try {
      const data = await api.getInterviewResults(meta);
      if (request !== resultsRequest.current) return;
      setResults(data);
      setResultsStatus('ready');
    } catch (e) {
      console.error(e);
      if (request === resultsRequest.current) setResultsStatus('error');
    }
  }, []);

  const showResults = useCallback((data) => {
    resultsRequest.current += 1;
    setResults(data);
    setResultsStatus('ready');
  }, []);

  /** After finishing an interview: reload history and skills from the server. */
  const refreshProgress = useCallback(() => { loadDashboardData(); }, [loadDashboardData]);

  /** After "Clear my practice data": forget local copies and reload (now empty) data. */
  const clearLocalData = useCallback(() => {
    resultsRequest.current += 1;
    setCvFile(null);
    setResults(null);
    setResultsStatus('idle');
    setHistory(null);
    setSkills(null);
    loadDashboardData();
  }, [loadDashboardData]);

  const value = useMemo(
    () => ({ user, setUser, cvFile, setCvFile, config, setConfig, history, skills, loadError, results, resultsStatus, openResults, showResults, refreshProgress, clearLocalData }),
    [user, setUser, cvFile, config, history, skills, loadError, results, resultsStatus, openResults, showResults, refreshProgress, clearLocalData],
  );
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}
