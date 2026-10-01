import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import Button from '../components/Button';
import Card from '../components/Card';
import InlineMessage from '../components/InlineMessage';
import InterviewProgress from '../components/InterviewProgress';
import QuestionCard from '../components/QuestionCard';
import ThinkingIndicator from '../components/ThinkingIndicator';
import { StaggerItem, StaggerList } from '../components/Reveal';
import { COACH_TIPS, MAX_ANSWER_LENGTH, MIN_ANSWER_LENGTH } from '../data/constants';
import { swap } from '../animations/variants';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useInterview } from '../hooks/useInterview';
import { useMounted } from '../hooks/useMounted';

export default function InterviewSession() {
  useDocumentTitle('Interview');
  const navigate = useNavigate();
  const mounted = useMounted();
  const { session, index, submitAnswer } = useInterview();
  const [answer, setAnswer] = useState('');
  const [phase, setPhase] = useState('answer'); // answer | loading
  const [error, setError] = useState('');

  if (!session) return null; // SessionGuard redirects when needed

  const question = session.questions[index];
  const total = session.questions.length;

  const submit = async () => {
    if (answer.trim().length < MIN_ANSWER_LENGTH) {
      return setError(`Please write at least ${MIN_ANSWER_LENGTH} characters so the AI can evaluate your answer.`);
    }
    setError('');
    setPhase('loading');
    try {
      const evaluation = await submitAnswer(answer);
      if (evaluation && mounted.current) navigate('/interview/evaluation');
    } catch {
      if (!mounted.current) return;
      setError('Evaluation failed. Please try again.');
      setPhase('answer');
    }
  };

  return (
    <div className="wrap">
      <InterviewProgress current={index + 1} total={total} config={session.config} progress={(index / total) * 100} onExit={() => navigate('/dashboard')} />
      <div className="main2">
        <div className="g">
          <QuestionCard question={question} slideIn={index > 0} />
          <AnimatePresence mode="wait" initial={false}>
            {phase === 'answer' ? (
              <motion.div key="answer" {...swap}>
                <Card enter={false}>
                  <label htmlFor="answer" className="sr-only">Your answer</label>
                  <textarea id="answer" placeholder="Type your answer here…" value={answer} maxLength={MAX_ANSWER_LENGTH} aria-describedby="answer-count" onChange={(e) => { setAnswer(e.target.value); setError(''); }} />
                  <div className="row sp mt-sm">
                    <span id="answer-count" className="mut">{answer.length} / {MAX_ANSWER_LENGTH}</span>
                  </div>
                  <InlineMessage message={error} />
                  <div className="row sp mt-md">
                    <Button disabled={!answer} onClick={() => setAnswer('')}>Clear</Button>
                    <Button variant="primary" onClick={submit}>Submit answer</Button>
                  </div>
                </Card>
              </motion.div>
            ) : (
              <motion.div key="loading" {...swap}>
                <Card><ThinkingIndicator /></Card>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
        <Card as="aside" enter tinted>
          <h3>🧭 Coach tip</h3>
          <p className="mut" style={{ margin: '8px 0' }}>Take your time. Focus on the problem, your approach, and the result.</p>
          <StaggerList className="l r" delay={0.4}>
            {COACH_TIPS.map((tip) => <StaggerItem as="li" key={tip}>{tip}</StaggerItem>)}
          </StaggerList>
        </Card>
      </div>
    </div>
  );
}
