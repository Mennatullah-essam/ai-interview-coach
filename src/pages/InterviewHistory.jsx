import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import Button from '../components/Button';
import Card from '../components/Card';
import Chip from '../components/Chip';
import PressableRow from '../components/PressableRow';
import Skeleton from '../components/Skeleton';
import { Reveal, Stagger } from '../components/Reveal';
import { HISTORY_FILTERS } from '../data/constants';
import { useApp } from '../hooks/useApp';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useOpenResults } from '../hooks/useOpenResults';
import { scoreLabel } from '../utils/scoring';

export default function InterviewHistory() {
  useDocumentTitle('Interview history');
  const { history } = useApp();
  const openResults = useOpenResults();
  const [filter, setFilter] = useState('All');

  if (!history) return <div className="wrap"><Skeleton n={4} /></div>;
  const list = history.filter((h) => filter === 'All' || h.type === filter);

  return (
    <div className="wrap">
      <Reveal className="row sp">
        <h2>Interview history</h2>
        <div className="row" role="group" aria-label="Filter by interview type">
          {HISTORY_FILTERS.map((t) => <Chip key={t} layoutId="history-pill" selected={filter === t} onClick={() => setFilter(t)}>{t}</Chip>)}
        </div>
      </Reveal>

      <Card enter className="mt-lg">
        <div className="tr hd" aria-hidden="true"><span>Role</span><span>Date</span><span>Type</span><span>Score</span><span>Qs</span><span>Status</span><span /></div>
        <AnimatePresence mode="wait" initial={false}>
          <motion.div key={filter} exit={{ opacity: 0 }} transition={{ duration: 0.12 }}>
            {list.length === 0 ? (
              <Reveal className="empty">
                <div className="big" aria-hidden="true">🗂️</div>
                <p className="mut">No {filter.toLowerCase()} interviews yet.</p>
                <Button variant="primary" className="mt-md" to="/cv-upload">Start one now</Button>
              </Reveal>
            ) : (
              <Stagger gap={0.06}>
                {list.map((h) => (
                  <PressableRow key={h.id} className="tr" label={`Review ${h.role} interview from ${h.date}`} onActivate={() => openResults(h)}>
                    <b>{h.role}</b>
                    <span className="mut">{h.date}</span>
                    <span>{h.type}</span>
                    <span><Chip tone={scoreLabel(h.score).tone}>{h.score}%</Chip></span>
                    <span>{h.n}</span>
                    <Chip tone="ok" style={{ justifySelf: 'start' }}>{h.status}</Chip>
                    <span style={{ color: 'var(--pri)' }}>Review →</span>
                  </PressableRow>
                ))}
              </Stagger>
            )}
          </motion.div>
        </AnimatePresence>
      </Card>
    </div>
  );
}
