import { createContext, useCallback, useMemo, useRef, useState } from 'react';
import api from '../services/api';
import { useApp } from '../hooks/useApp';

export const InterviewContext = createContext(null);

/**
 * State of the interview currently in progress.
 * `token` invalidates in-flight requests if the session is reset (e.g. the user exits).
 */
export function InterviewProvider({ children }) {
  const { config, addToHistory, showResults } = useApp();
  const [session, setSession] = useState(null);
  const [index, setIndex] = useState(0);
  const [items, setItems] = useState([]);
  const [currentEval, setCurrentEval] = useState(null);
  const [starting, setStarting] = useState(false);
  const token = useRef(0);

  const reset = useCallback(() => {
    token.current += 1;
    setSession(null);
    setIndex(0);
    setItems([]);
    setCurrentEval(null);
  }, []);

  const start = useCallback(async (cfg) => {
    setStarting(true);
    try {
      const created = await api.startInterview(cfg);
      token.current += 1;
      setSession({ ...created, config: cfg });
      setIndex(0);
      setItems([]);
      setCurrentEval(null);
      return created;
    } finally {
      setStarting(false);
    }
  }, []);

  /** Submits and evaluates the answer to the current question. Resolves null if the session was reset meanwhile. */
  const submitAnswer = useCallback(async (answer) => {
    const mine = token.current;
    const question = session.questions[index];
    await api.submitAnswer(session.id, index, answer);
    const ev = await api.getEvaluation(session.id, question, answer);
    if (mine !== token.current) return null;
    setCurrentEval(ev);
    setItems((x) => [...x, { q: question, ev }]);
    return ev;
  }, [session, index]);

  /** Moves to the next question (synchronous so the caller can navigate in the same render batch). */
  const advance = useCallback(() => {
    setIndex((i) => i + 1);
    setCurrentEval(null);
  }, []);

  /** Completes the interview after the last question. Resolves false if the session was reset meanwhile. */
  const finish = useCallback(async () => {
    const mine = token.current;
    const data = await api.completeInterview({ session, config: session.config ?? config, items });
    if (mine !== token.current) return false;
    addToHistory(data.meta);
    showResults(data);
    return true;
  }, [session, items, config, addToHistory, showResults]);

  const value = useMemo(
    () => ({ session, index, items, currentEval, starting, start, submitAnswer, advance, finish, reset }),
    [session, index, items, currentEval, starting, start, submitAnswer, advance, finish, reset],
  );
  return <InterviewContext.Provider value={value}>{children}</InterviewContext.Provider>;
}
