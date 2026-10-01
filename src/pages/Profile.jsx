import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import Button from '../components/Button';
import Card from '../components/Card';
import ConfirmModal from '../components/ConfirmModal';
import InlineMessage from '../components/InlineMessage';
import { Reveal } from '../components/Reveal';
import api from '../services/api';
import { useApp } from '../hooks/useApp';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useInterview } from '../hooks/useInterview';
import { useToast } from '../hooks/useToast';

export default function Profile() {
  useDocumentTitle('Profile & settings');
  const navigate = useNavigate();
  const { user, setUser, resetDemoData } = useApp();
  const { reset: resetInterview } = useInterview();
  const { say } = useToast();
  const [draft, setDraft] = useState(user);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const save = async () => {
    if (draft.name.trim().length < 2) return setError('Please enter your name.');
    if (!/^\S+@\S+\.\S+$/.test(draft.email)) return setError('Please enter a valid email.');
    setError('');
    setSaving(true);
    try {
      setUser(await api.updateProfile(draft));
      say('Profile saved');
    } catch {
      setError('Could not save your profile. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const confirmReset = () => {
    setConfirming(false);
    resetDemoData();
    resetInterview();
    say('Demo data reset');
    navigate('/dashboard');
  };

  return (
    <div className="wrap slim">
      <Reveal><h2>Profile &amp; settings</h2></Reveal>
      <Card enter className="g mt-lg">
        <label className="field">Full name
          <input type="text" value={draft.name} autoComplete="name" onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
        </label>
        <label className="field">Email
          <input type="email" value={draft.email} autoComplete="email" onChange={(e) => setDraft({ ...draft, email: e.target.value })} />
        </label>
        <InlineMessage message={error} />
        <div className="row">
          <Button variant="primary" disabled={saving} onClick={save}>{saving ? 'Saving…' : 'Save changes'}</Button>
          <Button onClick={() => setConfirming(true)}>Reset demo data</Button>
        </div>
      </Card>
      <AnimatePresence>
        {confirming && (
          <ConfirmModal title="Reset demo data?" text="This removes your uploaded CV and any new sessions." confirmLabel="Reset" onConfirm={confirmReset} onCancel={() => setConfirming(false)} />
        )}
      </AnimatePresence>
    </div>
  );
}
