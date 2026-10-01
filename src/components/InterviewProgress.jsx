import { useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import Card from './Card';
import Chip from './Chip';
import Button from './Button';
import ProgressBar from './ProgressBar';
import ConfirmModal from './ConfirmModal';

/** Header card of the interview screens: question counter, config chips, exit and progress. */
export default function InterviewProgress({ current, total, config, progress, onExit }) {
  const [leaving, setLeaving] = useState(false);
  return (
    <>
      <Card enter className="mb-lg">
        <div className="row sp">
          <b>Question {current} of {total}</b>
          <div className="row">
            <Chip>{config.role}</Chip>
            <Chip>{config.diff}</Chip>
            <Chip>{config.type}</Chip>
            <Button size="sm" onClick={() => setLeaving(true)}>Exit</Button>
          </div>
        </div>
        <ProgressBar className="mt-md" ariaLabel="Interview progress" value={progress} fast />
      </Card>
      <AnimatePresence>
        {leaving && (
          <ConfirmModal title="Exit interview?" text="Your progress in this session will be lost." confirmLabel="Exit" onConfirm={onExit} onCancel={() => setLeaving(false)} />
        )}
      </AnimatePresence>
    </>
  );
}
