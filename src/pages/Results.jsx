import { useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import Button from '../components/Button';
import Card from '../components/Card';
import Chip from '../components/Chip';
import Feedback from '../components/Feedback';
import Modal from '../components/Modal';
import PressableRow from '../components/PressableRow';
import ProgressBar from '../components/ProgressBar';
import ScoreCircle from '../components/ScoreCircle';
import Spinner from '../components/Spinner';
import { Stagger, StaggerItem, StaggerList } from '../components/Reveal';
import { useApp } from '../hooks/useApp';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { buildBreakdown, scoreLabel } from '../utils/scoring';

export default function Results() {
  useDocumentTitle('Interview results');
  const { results, resultsStatus } = useApp();
  const [selected, setSelected] = useState(null);

  if (resultsStatus === 'error') {
    return (
      <div className="wrap">
        <Card enter>
          <p>We couldn't load these results.</p>
          <Button className="mt-md" to="/history">Back to history</Button>
        </Card>
      </div>
    );
  }
  if (!results) return <div className="wrap"><Spinner label="Loading results…" className="mt-xl" /></div>;

  const { meta, items, recommendations, extraStrength, extraImprovement } = results;
  const breakdown = buildBreakdown(items);
  const ranked = Object.entries(breakdown).sort((a, b) => b[1] - a[1]);
  const overall = scoreLabel(meta.score);

  return (
    <Stagger className="wrap" gap={0.1}>
      <div className="row sp">
        <h2>Interview results</h2>
        <div className="row">
          <Button to="/dashboard">Back to Dashboard</Button>
          <Button variant="primary" to="/cv-upload">Practice Again</Button>
        </div>
      </div>

      <div className="g mt-lg">
        <Card className="row" style={{ gap: 28 }}>
          <ScoreCircle value={meta.score} size={160} label="Overall score" ariaLabel="Overall score" />
          <div style={{ flex: 1, minWidth: 240 }}>
            <h3>{meta.score}% Overall Score — <span className="grad">{overall.text}</span></h3>
            <div className="g g2 mt-md" style={{ gap: 8 }}>
              {[['Role', meta.role], ['Type', meta.type], ['Difficulty', meta.diff], ['Questions', meta.n], ['Completed', meta.date]].map(([label, value]) => (
                <div key={label}><span className="mut">{label}: </span><b>{value}</b></div>
              ))}
            </div>
          </div>
        </Card>

        <Card className="g">
          <h3>Performance breakdown</h3>
          <div className="g g2">
            {Object.entries(breakdown).map(([name, value], i) => <ProgressBar key={name} label={name} value={value} delay={0.3 + i * 0.1} />)}
          </div>
        </Card>

        <div className="g g3">
          <Card>
            <h3 className="mb-md">Strengths</h3>
            <StaggerList className="l s">
              {ranked.slice(0, 2).map(([name, value]) => <StaggerItem as="li" key={name}>{name} ({value}%)</StaggerItem>)}
              <StaggerItem as="li">{extraStrength}</StaggerItem>
            </StaggerList>
          </Card>
          <Card>
            <h3 className="mb-md">Areas for improvement</h3>
            <StaggerList className="l w">
              {ranked.slice(-2).reverse().map(([name, value]) => <StaggerItem as="li" key={name}>{name} ({value}%)</StaggerItem>)}
              <StaggerItem as="li">{extraImprovement}</StaggerItem>
            </StaggerList>
          </Card>
          <Card>
            <h3 className="mb-md">AI recommendations</h3>
            <StaggerList className="l r">
              {recommendations.map((r) => <StaggerItem as="li" key={r}>{r}</StaggerItem>)}
            </StaggerList>
          </Card>
        </div>

        <Card>
          <h3>Question-by-question</h3>
          <p className="mut mb-sm">Select a question to see detailed feedback.</p>
          <div className="qr hd" aria-hidden="true"><span>Question</span><span>Score</span><span>Status</span></div>
          <StaggerList as="div" gap={0.05} delay={0.2}>
            {items.map((x, i) => {
              const label = scoreLabel(x.ev.score);
              return (
                <PressableRow key={i} className="qr" label={`Question ${i + 1}, score ${x.ev.score}%. Open feedback`} onActivate={() => setSelected(x)}>
                  <span><b>Q{i + 1}.</b> {x.q.text}</span>
                  <b>{x.ev.score}%</b>
                  <span><Chip tone={label.tone}>{label.text}</Chip></span>
                </PressableRow>
              );
            })}
          </StaggerList>
        </Card>
      </div>

      <AnimatePresence>
        {selected && (
          <Modal onClose={() => setSelected(null)} ariaLabel={`Feedback: ${selected.q.text}`}>
            <div className="row sp mb-md" style={{ flexWrap: 'nowrap', alignItems: 'flex-start' }}>
              <h3 style={{ flex: 1 }}>{selected.q.text}</h3>
              <Button aria-label="Close feedback" onClick={() => setSelected(null)}>✕</Button>
            </div>
            <Feedback evaluation={selected.ev} />
          </Modal>
        )}
      </AnimatePresence>
    </Stagger>
  );
}
