import { useContext } from 'react';
import { InterviewContext } from '../context/InterviewContext';

export function useInterview() {
  const ctx = useContext(InterviewContext);
  if (!ctx) throw new Error('useInterview must be used inside <InterviewProvider>');
  return ctx;
}
