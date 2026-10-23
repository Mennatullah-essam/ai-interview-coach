import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import AnimatedValue from '../components/AnimatedValue';
import Button from '../components/Button';
import Card from '../components/Card';
import Chip from '../components/Chip';
import InlineMessage from '../components/InlineMessage';
import OptionCard from '../components/OptionCard';
import { Reveal } from '../components/Reveal';
import { DIFFICULTIES, INTERVIEW_TYPES, MAX_JOB_DESCRIPTION_LENGTH, MIN_CUSTOM_ROLE_LENGTH, MINUTES_PER_QUESTION, QUESTION_COUNTS, ROLES } from '../data/constants';
import { ease } from '../animations/variants';
import { useApp } from '../hooks/useApp';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useInterview } from '../hooks/useInterview';
import { useMounted } from '../hooks/useMounted';
import api, { errorMessage } from '../services/api';

/** Tells the candidate whether their reviewed profile will personalise the questions. */
function PersonalizationNotice({ state }) {
  if (state === 'loading') return <p className="mut" role="status">Checking your profile…</p>;
  if (state === 'confirmed') {
    return <div className="note ok">✓ Personalised with your reviewed profile: questions use your projects, skills and possible skill gaps. <Link to="/profile/review">Edit profile</Link></div>;
  }
  if (state === 'draft') {
    return <div className="note warn">Your CV profile has not been reviewed yet, so questions use only your CV skills and the role. <Link to="/profile/review">Review your profile</Link> to personalise them.</div>;
  }
  if (state === 'error') return <div className="note">Could not check your profile. Questions will be based on your CV skills and the role.</div>;
  return null;
}

export default function InterviewSetup() {
  useDocumentTitle('Set up your interview');
  const navigate = useNavigate();
  const mounted = useMounted();
  const { cvFile, config, setConfig } = useApp();
  const { start, starting } = useInterview();
  const [custom, setCustom] = useState('');
  const [error, setError] = useState('');
  const [profileState, setProfileState] = useState('loading'); // loading | none | draft | confirmed | error
  const [intelligence, setIntelligence] = useState(null);

  useEffect(() => {
    let active = true;
    api.getCandidateProfile()
      .then((p) => { if (active) setProfileState(p ? p.status : 'none'); })
      .catch((e) => { console.error(e); if (active) setProfileState('error'); });
    api.getIntelligenceStatus().then((s) => { if (active) setIntelligence(s); });
    return () => { active = false; };
  }, []);

  if (!cvFile) {
    return (
      <div className="wrap">
        <Card enter>
          Please upload your CV first. <Button variant="primary" to="/cv-upload">Upload CV</Button>
        </Card>
      </div>
    );
  }

  const customRole = custom.trim();
  const role = customRole || config.role;
  const set = (key, value) => setConfig({ ...config, [key]: value });

  const begin = async () => {
    if (!role) return setError('Please select or enter a target job role.');
    if (customRole && customRole.length < MIN_CUSTOM_ROLE_LENGTH) return setError(`Custom role must be at least ${MIN_CUSTOM_ROLE_LENGTH} characters.`);
    if ((config.jobDescription ?? '').length > MAX_JOB_DESCRIPTION_LENGTH) return setError(`The job description can be at most ${MAX_JOB_DESCRIPTION_LENGTH} characters.`);
    const finalConfig = { ...config, role };
    setConfig(finalConfig);
    try {
      await start(finalConfig, cvFile.id);
      if (mounted.current) navigate('/interview/session');
    } catch (e) {
      if (mounted.current) setError(errorMessage(e, 'Could not prepare your questions. Please try again.'));
    }
  };

  const summary = [
    ['Role', role || '—'],
    ['Type', config.type],
    ['Difficulty', config.diff],
    ['Questions', config.n],
    ['Follow-ups', config.adaptive ? 'Adaptive' : 'Off'],
    ['Personalised', profileState === 'confirmed' ? 'Yes' : 'No'],
    ['Matching', intelligence?.embeddings === 'sbert' ? 'Local AI model' : 'Rules + synonyms'],
    ['Follow-up AI', intelligence?.llm === 'active' && intelligence.llm_features?.includes('agent') ? 'AI model + rules' : 'Rules'],
    ['Est. time', `~${config.n * MINUTES_PER_QUESTION} min`],
  ];

  return (
    <div className="wrap">
      <Reveal>
        <h2>Set up your interview</h2>
        <p className="mut lead">CV: <b>{cvFile.name}</b></p>
      </Reveal>
      <div className="main2">
        <Card enter className="g" style={{ gap: 22 }}>
          <PersonalizationNotice state={profileState} />
          <section aria-labelledby="role-h">
            <h3 id="role-h" className="mb-sm">Target job role</h3>
            <div className="row" role="group" aria-labelledby="role-h">
              {ROLES.map((r) => (
                <Chip key={r} layoutId="role-pill" selected={!customRole && config.role === r} onClick={() => { setCustom(''); set('role', r); setError(''); }}>{r}</Chip>
              ))}
            </div>
            <input type="text" className="mt-md" aria-label="Custom job role" aria-describedby={error ? 'role-error' : undefined} placeholder="Or type a custom role, e.g. NLP Researcher" value={custom} onChange={(e) => { setCustom(e.target.value); setError(''); }} />
            <InlineMessage id="role-error" message={error} />
          </section>

          <section aria-labelledby="type-h">
            <h3 id="type-h" className="mb-sm">Interview type</h3>
            <div className="row" role="group" aria-labelledby="type-h">
              {INTERVIEW_TYPES.map((t) => (
                <OptionCard key={t.value} layoutId="type-ring" title={`${t.value} Interview`} description={t.description} selected={config.type === t.value} onClick={() => set('type', t.value)} />
              ))}
            </div>
          </section>

          <section aria-labelledby="diff-h">
            <h3 id="diff-h" className="mb-sm">Difficulty</h3>
            <div className="row" role="group" aria-labelledby="diff-h">
              {DIFFICULTIES.map((d) => <Chip key={d} size="lg" layoutId="diff-pill" selected={config.diff === d} onClick={() => set('diff', d)}>{d}</Chip>)}
            </div>
          </section>

          <section aria-labelledby="count-h">
            <h3 id="count-h" className="mb-sm">Number of questions</h3>
            <div className="row" role="group" aria-labelledby="count-h">
              {QUESTION_COUNTS.map((n) => <Chip key={n} size="xl" layoutId="count-pill" selected={config.n === n} onClick={() => set('n', n)}>{n}</Chip>)}
            </div>
          </section>

          <section aria-labelledby="jd-h">
            <h3 id="jd-h" className="mb-sm">Job description <span className="mut" style={{ fontWeight: 500, fontSize: '0.9rem' }}>(optional)</span></h3>
            <p className="mut mb-sm" style={{ fontSize: '0.9rem' }}>Paste a job ad and questions will focus on the skills it asks for.</p>
            <textarea className="short" aria-labelledby="jd-h" aria-describedby="jd-count" placeholder="e.g. We are looking for a backend developer with Python, PostgreSQL and Docker…" maxLength={MAX_JOB_DESCRIPTION_LENGTH} value={config.jobDescription ?? ''} onChange={(e) => set('jobDescription', e.target.value)} />
            <span id="jd-count" className="mut" style={{ fontSize: '0.85rem' }}>{(config.jobDescription ?? '').length} / {MAX_JOB_DESCRIPTION_LENGTH}</span>
          </section>

          <section aria-labelledby="adaptive-h">
            <h3 id="adaptive-h" className="mb-sm">Adaptive follow-ups</h3>
            <label className="switch">
              <input type="checkbox" checked={Boolean(config.adaptive)} onChange={(e) => set('adaptive', e.target.checked)} />
              <span>
                <b>Ask follow-up questions</b>
                <span className="mut" style={{ display: 'block', fontSize: '0.9rem' }}>
                  After a vague or incomplete answer you may get a clarifying question; after a strong one, a deeper question.
                  Up to {config.n === 5 ? 2 : config.n === 10 ? 3 : 4} follow-ups, and later questions may get easier or harder.
                </span>
              </span>
            </label>
          </section>
        </Card>

        <motion.aside className="card g summary" aria-label="Interview summary" initial={{ opacity: 0, x: 28 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.5, ease, delay: 0.2 }}>
          <h3>Interview summary</h3>
          {summary.map(([label, value]) => (
            <div key={label} className="row sp">
              <span className="mut">{label}</span>
              <AnimatedValue value={value} />
            </div>
          ))}
          <Button variant="primary" disabled={starting} onClick={begin}>
            {starting ? (<><span className="spin sm" aria-hidden="true" />Preparing questions…</>) : 'Start Interview'}
          </Button>
          <Button onClick={() => navigate('/cv-upload')}>← Back</Button>
        </motion.aside>
      </div>
    </div>
  );
}
