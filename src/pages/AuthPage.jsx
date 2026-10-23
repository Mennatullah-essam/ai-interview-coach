import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import Button from '../components/Button';
import Card from '../components/Card';
import InlineMessage from '../components/InlineMessage';
import Navbar from '../components/Navbar';
import { Reveal } from '../components/Reveal';
import { errorMessage } from '../services/api';
import { useAuth } from '../hooks/useAuth';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useMounted } from '../hooks/useMounted';

const EMAIL_RE = /^\S+@\S+\.\S+$/;
const MIN_PASSWORD = 8;

const COPY = {
  login: {
    title: 'Log in',
    heading: 'Welcome back',
    lead: 'Log in to continue practising and see your progress.',
    submit: 'Log in',
    busy: 'Logging in…',
    switchText: 'New here?',
    switchLink: 'Create an account',
    switchTo: '/signup',
  },
  signup: {
    title: 'Sign up',
    heading: 'Create your account',
    lead: 'Your CVs, interviews and feedback are private to your account.',
    submit: 'Create account',
    busy: 'Creating account…',
    switchText: 'Already have an account?',
    switchLink: 'Log in',
    switchTo: '/login',
  },
};

/** Shared Login / Sign up screen (mode = "login" | "signup"). */
export default function AuthPage({ mode }) {
  const copy = COPY[mode];
  useDocumentTitle(copy.title);
  const navigate = useNavigate();
  const location = useLocation();
  const mounted = useMounted();
  const { signIn, signUp, notice, clearNotice } = useAuth();
  const [form, setForm] = useState({ name: '', email: '', password: '', confirm: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const isSignup = mode === 'signup';

  const set = (key) => (e) => { setForm({ ...form, [key]: e.target.value }); setError(''); };

  const validate = () => {
    if (isSignup && form.name.trim().length < 2) return 'Please enter your name (at least 2 characters).';
    if (!EMAIL_RE.test(form.email.trim())) return 'Please enter a valid email address.';
    if (!form.password) return 'Please enter your password.';
    if (isSignup && form.password.length < MIN_PASSWORD) return `Your password must be at least ${MIN_PASSWORD} characters.`;
    if (isSignup && form.password !== form.confirm) return 'The passwords do not match.';
    return '';
  };

  const submit = async (e) => {
    e.preventDefault();
    const problem = validate();
    if (problem) return setError(problem);
    setBusy(true);
    clearNotice();
    try {
      if (isSignup) await signUp({ name: form.name.trim(), email: form.email.trim(), password: form.password });
      else await signIn({ email: form.email.trim(), password: form.password });
      navigate(location.state?.from || '/dashboard', { replace: true });
    } catch (err) {
      if (mounted.current) setError(errorMessage(err, isSignup ? 'Could not create your account. Please try again.' : 'Could not log you in. Please try again.'));
    } finally {
      if (mounted.current) setBusy(false);
    }
  };

  return (
    <>
      <a href="#main" className="skip-link">Skip to content</a>
      <Navbar variant="landing" />
      <main id="main" tabIndex={-1} className="wrap slim">
        <Reveal className="center">
          <h2>{copy.heading}</h2>
          <p className="mut lead">{copy.lead}</p>
        </Reveal>
        <InlineMessage variant="box" message={notice} />
        <Card enter className="mt-lg">
          <form className="g" onSubmit={submit} noValidate aria-label={copy.title}>
            {isSignup && (
              <label className="field">Full name
                <input type="text" name="name" autoComplete="name" value={form.name} onChange={set('name')} maxLength={100} required />
              </label>
            )}
            <label className="field">Email
              <input type="email" name="email" autoComplete="email" value={form.email} onChange={set('email')} maxLength={254} required />
            </label>
            <label className="field">Password
              <input type="password" name="password" autoComplete={isSignup ? 'new-password' : 'current-password'} value={form.password} onChange={set('password')} maxLength={128} required aria-describedby={isSignup ? 'pw-hint' : undefined} />
              {isSignup && <span id="pw-hint" className="mut" style={{ fontWeight: 400 }}>At least {MIN_PASSWORD} characters.</span>}
            </label>
            {isSignup && (
              <label className="field">Confirm password
                <input type="password" name="confirm" autoComplete="new-password" value={form.confirm} onChange={set('confirm')} maxLength={128} required />
              </label>
            )}
            <InlineMessage message={error} />
            <Button variant="primary" type="submit" disabled={busy}>
              {busy ? (<><span className="spin sm" aria-hidden="true" />{copy.busy}</>) : copy.submit}
            </Button>
          </form>
        </Card>
        <p className="center mut mt-lg">
          {copy.switchText} <Link to={copy.switchTo} state={location.state}>{copy.switchLink}</Link>
        </p>
      </main>
    </>
  );
}
