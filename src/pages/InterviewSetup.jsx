import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import AnimatedValue from '../components/AnimatedValue';
import Button from '../components/Button';
import Card from '../components/Card';
import Chip from '../components/Chip';
import InlineMessage from '../components/InlineMessage';
import OptionCard from '../components/OptionCard';
import { Reveal } from '../components/Reveal';
import { DIFFICULTIES, INTERVIEW_TYPES, MIN_CUSTOM_ROLE_LENGTH, MINUTES_PER_QUESTION, QUESTION_COUNTS, ROLES } from '../data/constants';
import { ease } from '../animations/variants';
import { useApp } from '../hooks/useApp';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useInterview } from '../hooks/useInterview';
import { useMounted } from '../hooks/useMounted';

export default function InterviewSetup() {
  useDocumentTitle('Set up your interview');
  const navigate = useNavigate();
  const mounted = useMounted();
  const { cvFile, config, setConfig } = useApp();
  const { start, starting } = useInterview();
  const [custom, setCustom] = useState('');
  const [error, setError] = useState('');

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
    const finalConfig = { ...config, role };
    setConfig(finalConfig);
    try {
      await start(finalConfig);
      if (mounted.current) navigate('/interview/session');
    } catch {
      if (mounted.current) setError('Could not generate questions. Please try again.');
    }
  };

  const summary = [
    ['Role', role || '—'],
    ['Type', config.type],
    ['Difficulty', config.diff],
    ['Questions', config.n],
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
            {starting ? (<><span className="spin sm" aria-hidden="true" />Generating questions…</>) : 'Start Interview'}
          </Button>
          <Button onClick={() => navigate('/cv-upload')}>← Back</Button>
        </motion.aside>
      </div>
    </div>
  );
}
