import { createContext, useCallback, useEffect, useMemo, useState } from 'react';
import api, { setSessionExpiredHandler } from '../services/api';

export const AuthContext = createContext(null);

/**
 * The signed-in user, from the real backend session.
 * status: 'loading' (checking the refresh cookie) | 'authenticated' | 'anonymous'.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState('loading');
  const [notice, setNotice] = useState('');

  useEffect(() => {
    let active = true;
    setSessionExpiredHandler(() => {
      setUser(null);
      setStatus('anonymous');
      setNotice('Your session has expired. Please log in again.');
    });
    api.restoreSession()
      .then((restored) => {
        if (!active) return;
        setUser(restored);
        setStatus(restored ? 'authenticated' : 'anonymous');
      })
      .catch(() => { if (active) setStatus('anonymous'); });
    return () => { active = false; };
  }, []);

  const signIn = useCallback(async (credentials) => {
    const signedIn = await api.login(credentials);
    setNotice('');
    setUser(signedIn);
    setStatus('authenticated');
    return signedIn;
  }, []);

  const signUp = useCallback(async (details) => {
    const created = await api.register(details);
    setNotice('');
    setUser(created);
    setStatus('authenticated');
    return created;
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setUser(null);
      setStatus('anonymous');
    }
  }, []);

  const value = useMemo(
    () => ({ user, status, notice, setUser, signIn, signUp, signOut, clearNotice: () => setNotice('') }),
    [user, status, notice, signIn, signUp, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
