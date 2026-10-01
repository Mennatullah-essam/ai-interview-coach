import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from './useApp';

/** Returns a function that opens the results screen for a past interview. */
export function useOpenResults() {
  const { openResults } = useApp();
  const navigate = useNavigate();
  return useCallback((meta) => {
    openResults(meta);
    navigate('/results');
  }, [openResults, navigate]);
}
