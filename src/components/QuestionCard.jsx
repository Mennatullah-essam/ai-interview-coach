import { motion } from 'framer-motion';
import Card from './Card';
import Chip from './Chip';
import { ease } from '../animations/variants';

/** Shows the current question. With `slideIn` it enters from the right, like a new card being dealt. */
export default function QuestionCard({ question, slideIn = false }) {
  return (
    <Card
      as="section"
      aria-label="Current question"
      initial={{ opacity: 0, x: slideIn ? 32 : 0, y: slideIn ? 0 : 12 }}
      animate={{ opacity: 1, x: 0, y: 0, transition: { duration: 0.45, ease } }}
    >
      <Chip tone={question.type === 'Technical' ? 'blue' : 'ok'}>{question.type} Question</Chip>
      <motion.p className="q" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.15, duration: 0.4 }}>
        {question.text}
      </motion.p>
    </Card>
  );
}
