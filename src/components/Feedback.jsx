import { useId, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import Card from './Card';
import Button from './Button';
import Chip from './Chip';
import ProgressBar from './ProgressBar';
import ScoreCircle from './ScoreCircle';
import { Stagger, StaggerItem, StaggerList } from './Reveal';
import { ease } from '../animations/variants';

/** Evaluation panel shared by the Evaluation page and the Results detail modal. */
export default function Feedback({ evaluation }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();

  return (
    <Stagger className="g" gap={0.12}>
      <Card className="row" style={{ gap: 24 }}>
        <ScoreCircle value={evaluation.score} ariaLabel="Answer score" />
        <div className="g metric-list">
          {Object.entries(evaluation.cats).map(([name, value], i) => (
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

      <Card tinted>
        <h3>💡 Improvement suggestion</h3>
        <p className="mt-sm">{evaluation.tip}</p>
      </Card>

      <Card>
        <Button onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-controls={panelId}>
          {open ? 'Hide' : 'View'} an example of a stronger answer {open ? '▴' : '▾'}
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
