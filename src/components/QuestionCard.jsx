import { motion } from 'framer-motion';
import Card from './Card';
import Chip from './Chip';
import { ease } from '../animations/variants';
import { QUESTION_CATEGORIES } from '../data/constants';

/** Shows the current question. With `slideIn` it enters from the right, like a new card being dealt. */
export default function QuestionCard({ question, slideIn = false }) {
  const followUp = question.category === 'follow_up';
  const category = QUESTION_CATEGORIES[question.category];
  return (
    <Card
      as="section"
      aria-label={followUp ? 'Follow-up question' : 'Current question'}
      initial={{ opacity: 0, x: slideIn ? 32 : 0, y: slideIn ? 0 : 12 }}
      animate={{ opacity: 1, x: 0, y: 0, transition: { duration: 0.45, ease } }}
    >
      <div className="row" style={{ gap: 8 }}>
        <Chip tone={question.type === 'Technical' ? 'blue' : 'ok'}>{question.type} Question</Chip>
        {followUp && <Chip tone="warn">↳ Follow-up</Chip>}
        {!followUp && category && question.category !== 'behavioral' && <Chip tone="muted">{category}</Chip>}
      </div>
      <motion.p className="q" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.15, duration: 0.4 }}>
        {question.text}
      </motion.p>
      {question.reason && (
        <p className="why"><b>Why this question:</b> {question.reason}</p>
      )}
    </Card>
  );
}
