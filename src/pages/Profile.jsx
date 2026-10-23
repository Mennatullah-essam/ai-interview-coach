import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import Button from '../components/Button';
import Card from '../components/Card';
import ConfirmModal from '../components/ConfirmModal';
import InlineMessage from '../components/InlineMessage';
import { Reveal } from '../components/Reveal';
import api, { errorMessage } from '../services/api';
import { useApp } from '../hooks/useApp';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useInterview } from '../hooks/useInterview';
import { useToast } from '../hooks/useToast';

export default function Profile() {
  useDocumentTitle('Profile & settings');
  const navigate = useNavigate();
  const { user, setUser, clearLocalData } = useApp();
  const { reset: resetInterview } = useInterview();
  const { say } = useToast();
  const [draft, setDraft] = useState({ name: user?.name ?? '', email: user?.email ?? '' });
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [clearing, setClearing] = useState(false);

  const save = async () => {
    if (draft.name.trim().length < 2) return setError('Please enter your name.');
    if (!/^\S+@\S+\.\S+$/.test(draft.email)) return setError('Please enter a valid email.');
    setError('');
    setSaving(true);
    try {
      const saved = await api.updateProfile({ name: draft.name.trim(), email: draft.email.trim() });
      setUser(saved);
      setDraft({ name: saved.name, email: saved.email });
      say('Profile saved');
    } catch (e) {
      setError(errorMessage(e, 'Could not save your profile. Please try again.'));
    } finally {
      setSaving(false);
    }
  };

  const confirmReset = async () => {
    setConfirming(false);
    setClearing(true);
    try {
      await api.clearMyData();
      resetInterview();
      clearLocalData();
      say('Your practice data was deleted');
      navigate('/dashboard');
    } catch (e) {
      setError(errorMessage(e, 'Could not delete your data. Please try again.'));
    } finally {
      setClearing(false);
    }
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
          <Button disabled={clearing} onClick={() => setConfirming(true)}>{clearing ? 'Deleting…' : 'Delete my practice data'}</Button>
        </div>
      </Card>
      <Card className="row sp mt-md">
        <div>
          <h3>CV profile</h3>
          <p className="mut" style={{ fontSize: '0.9rem' }}>Skills, experience and projects extracted from your CV, used to personalise interviews.</p>
        </div>
        <Button to="/profile/review">Review profile →</Button>
      </Card>
      <AnimatePresence>
        {confirming && (
          <ConfirmModal title="Delete your practice data?" text="This permanently deletes your uploaded CVs, your CV profile, and all of your interviews, results and improvement plans. Your account stays." confirmLabel="Delete" onConfirm={confirmReset} onCancel={() => setConfirming(false)} />
        )}
      </AnimatePresence>
    </div>
  );
}
