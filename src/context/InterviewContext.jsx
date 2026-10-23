import { createContext, useCallback, useMemo, useRef, useState } from 'react';
import api from '../services/api';
import { useApp } from '../hooks/useApp';

export const InterviewContext = createContext(null);

/**
 * State of the interview currently in progress.
 * `token` invalidates in-flight requests if the session is reset (e.g. the user exits).
 */
export function InterviewProvider({ children }) {
  const { refreshProgress, showResults } = useApp();
  const [session, setSession] = useState(null);
  const [index, setIndex] = useState(0);
  const [currentEval, setCurrentEval] = useState(null);
  const [starting, setStarting] = useState(false);
  const token = useRef(0);

  const reset = useCallback(() => {
    token.current += 1;
    setSession(null);
    setIndex(0);
    setCurrentEval(null);
  }, []);

  /** Creates the interview on the server for the given config and CV id. */
  const start = useCallback(async (cfg, cvId) => {
    setStarting(true);
    try {
      const created = await api.startInterview(cfg, cvId);
      token.current += 1;
      setSession({ ...created, config: { ...cfg, ...created.server } });
      setIndex(0);
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
    await api.submitAnswer(session.id, question.id, answer);
    const ev = await api.getEvaluation(session.id, question);
    if (mine !== token.current) return null;
    // Adaptive interviews: the server may add a follow-up right after this question
    // and/or adjust the difficulty of a later one. Mirror both locally.
    if (ev.followUp || ev.replaced) {
      setSession((current) => {
        let questions = current.questions;
        if (ev.replaced) questions = questions.map((q) => (q.id === ev.replaced.id ? ev.replaced : q));
        if (ev.followUp && !questions.some((q) => q.id === ev.followUp.id)) {
          const at = questions.findIndex((q) => q.id === question.id) + 1;
          questions = [...questions.slice(0, at), ev.followUp, ...questions.slice(at)];
        }
        return { ...current, questions: questions.map((q, i) => ({ ...q, position: i + 1 })) };
      });
    }
    setCurrentEval(ev);
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
    const data = await api.completeInterview({ session });
    if (mine !== token.current) return false;
    showResults(data);
    refreshProgress();
    return true;
  }, [session, showResults, refreshProgress]);

  /** "Exit interview": tell the server (best effort) so it is excluded from history. */
  const abandon = useCallback(() => {
    if (session) api.abandonInterview(session.id).catch((e) => console.error(e));
  }, [session]);

  const value = useMemo(
    () => ({ session, index, currentEval, starting, start, submitAnswer, advance, finish, abandon, reset }),
    [session, index, currentEval, starting, start, submitAnswer, advance, finish, abandon, reset],
  );
  return <InterviewContext.Provider value={value}>{children}</InterviewContext.Provider>;
}
