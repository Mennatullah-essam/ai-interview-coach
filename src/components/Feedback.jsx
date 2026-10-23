import { useId, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import Card from './Card';
import Button from './Button';
import Chip from './Chip';
import ProgressBar from './ProgressBar';
import ScoreCircle from './ScoreCircle';
import ConceptEvidence from './ConceptEvidence';
import { Stagger, StaggerItem, StaggerList } from './Reveal';
import { ease } from '../animations/variants';

const FALLBACK_NOTE = 'Automated estimate for practice. It is not a hiring assessment.';

/** Evaluation panel shared by the Evaluation page and the Results detail modal. */
export default function Feedback({ evaluation }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const dimensions = evaluation.dimensions?.length ? evaluation.dimensions : null;
  const suggestions = evaluation.suggestions?.length ? evaluation.suggestions : [evaluation.tip].filter(Boolean);

  return (
    <Stagger className="g" gap={0.12}>
      <Card className="row" style={{ gap: 24, alignItems: 'flex-start' }}>
        <ScoreCircle value={evaluation.score} ariaLabel="Answer score" />
        <div className="g metric-list" style={{ gap: 4 }}>
          {dimensions
            ? dimensions.map((d, i) => (
              <div key={d.key}>
                {d.score === null || d.score === undefined ? (
                  <div className="row sp bar-head"><span>{d.label}</span><span className="mut">not assessed</span></div>
                ) : (
                  <ProgressBar label={d.label} value={d.score} delay={0.35 + i * 0.08} />
                )}
                <p className="dim-note">{d.explanation}</p>
              </div>
            ))
            : Object.entries(evaluation.cats).map(([name, value], i) => (
              <ProgressBar key={name} label={name} value={value} delay={0.35 + i * 0.1} />
            ))}
        </div>
      </Card>

      <div className="g g2">
        <Card>
          <h3 className="mb-md">Strengths</h3>
          <StaggerList className="l s">
            {evaluation.strengths.map((s) => <StaggerItem as="li" key={s}>{s}</StaggerItem>)}
          </StaggerList>
        </Card>
        <Card>
          <h3 className="mb-md">Weaknesses</h3>
          <StaggerList className="l w">
            {evaluation.weaknesses.map((w) => <StaggerItem as="li" key={w}>{w}</StaggerItem>)}
          </StaggerList>
        </Card>
      </div>

      <ConceptEvidence evaluation={evaluation} />

      {!evaluation.concepts?.length && evaluation.missing?.length > 0 && (
        <Card>
          <h3 className="mb-sm">Missing concepts</h3>
          <p className="mut mb-sm" style={{ fontSize: '0.88rem' }}>Key points a strong answer to this question usually covers, which we did not find in yours.</p>
          <div className="row" style={{ gap: 8 }}>
            {evaluation.missing.map((m) => <Chip key={m} tone="warn">{m}</Chip>)}
          </div>
        </Card>
      )}

      <Card tinted>
        <h3>💡 {suggestions.length > 1 ? 'How to improve' : 'Improvement suggestion'}</h3>
        {suggestions.length > 1 ? (
          <StaggerList className="l r mt-sm">
            {suggestions.map((s) => <StaggerItem as="li" key={s}>{s}</StaggerItem>)}
          </StaggerList>
        ) : (
          <p className="mt-sm">{suggestions[0]}</p>
        )}
      </Card>

      <p className="mut" style={{ fontSize: '0.85rem' }}>
        {evaluation.explanation || FALLBACK_NOTE}
        {evaluation.feedbackSource === 'hybrid' && ' Scores combine rule-based checks with a bounded AI model review.'}
      </p>

      <Card>
        <Button onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-controls={panelId}>
          {open ? 'Hide' : 'View'} a stronger answer {open ? '▴' : '▾'}
        </Button>
        <AnimatePresence initial={false}>
          {open && (
            <motion.div
              id={panelId}
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.3, ease }}
              style={{ overflow: 'hidden' }}
            >
              {evaluation.outline?.length > 0 && (
                <div className="ideal">
                  <Chip tone="blue">Answer outline</Chip>
                  <ol className="mt-sm" style={{ paddingLeft: 20, display: 'grid', gap: 4 }}>
                    {evaluation.outline.map((point) => <li key={point}>{point}</li>)}
                  </ol>
                </div>
              )}
              <div className="ideal">
                <Chip tone="blue">Example — not your answer</Chip>
                <p>{evaluation.ideal}</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </Card>
    </Stagger>
  );
}
