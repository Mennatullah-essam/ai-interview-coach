import { createContext, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import api from '../services/api';
import { DEMO_USER } from '../data/mockData';
import { DEFAULT_CONFIG } from '../data/constants';

export const AppContext = createContext(null);

/** Holds user, CV, interview configuration, history, skills and the currently viewed results. */
export function AppProvider({ children }) {
  const [user, setUser] = useState(DEMO_USER); // TODO(backend): load from the authenticated user.
  const [cvFile, setCvFile] = useState(null);
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  const [history, setHistory] = useState(null);
  const [skills, setSkills] = useState(null);
  const [results, setResults] = useState(null);
  const [resultsStatus, setResultsStatus] = useState('idle'); // idle | loading | ready | error
  const resultsRequest = useRef(0);

  const loadDashboardData = useCallback(() => {
    api.getInterviewHistory().then(setHistory).catch((e) => { console.error(e); setHistory([]); });
    api.getSkills().then(setSkills).catch((e) => { console.error(e); setSkills({}); });
  }, []);

  useEffect(() => { loadDashboardData(); }, [loadDashboardData]);

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

  const addToHistory = useCallback((meta) => setHistory((h) => [meta, ...(h ?? [])]), []);

  const resetDemoData = useCallback(() => {
    resultsRequest.current += 1;
    setCvFile(null);
    setResults(null);
    setResultsStatus('idle');
    setHistory(null);
    loadDashboardData();
  }, [loadDashboardData]);

  const value = useMemo(
    () => ({ user, setUser, cvFile, setCvFile, config, setConfig, history, skills, results, resultsStatus, openResults, showResults, addToHistory, resetDemoData }),
    [user, cvFile, config, history, skills, results, resultsStatus, openResults, showResults, addToHistory, resetDemoData],
  );
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}
