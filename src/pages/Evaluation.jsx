import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../components/Button';
import AgentDecision from '../components/AgentDecision';
import Feedback from '../components/Feedback';
import InlineMessage from '../components/InlineMessage';
import InterviewProgress from '../components/InterviewProgress';
import QuestionCard from '../components/QuestionCard';
import { Reveal } from '../components/Reveal';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useInterview } from '../hooks/useInterview';
import { useMounted } from '../hooks/useMounted';
import { errorMessage } from '../services/api';

export default function Evaluation() {
  useDocumentTitle('Answer evaluation');
  const navigate = useNavigate();
  const mounted = useMounted();
  const { session, index, currentEval, advance, finish, abandon } = useInterview();
  const [finishing, setFinishing] = useState(false);
  const [error, setError] = useState('');

  // Keep the last valid data so the page can fade out cleanly after advancing/finishing.
  const retained = useRef(null);
  if (session && currentEval) retained.current = { session, index, evaluation: currentEval };
  if (!retained.current) return null; // EvaluationGuard redirects when needed
  const { session: s, index: i, evaluation } = retained.current;

  const total = s.questions.length;
  const isLast = i + 1 >= total;
  const nextQuestion = s.questions[i + 1];
  const followUpNext = nextQuestion?.category === 'follow_up' && nextQuestion.parentId === s.questions[i].id;

  const next = async () => {
    if (!isLast) {
      advance();
      navigate('/interview/session');
      return;
    }
    setFinishing(true);
    setError('');
    try {
      const ok = await finish();
      if (ok && mounted.current) navigate('/results');
    } catch (e) {
      if (!mounted.current) return;
      setError(errorMessage(e, 'Could not load your results. Please try again.'));
      setFinishing(false);
    }
  };

  return (
    <div className="wrap">
      <InterviewProgress current={i + 1} total={total} config={s.config} progress={((i + 1) / total) * 100} onExit={() => { abandon(); navigate('/dashboard'); }} />
      <div className="g">
        <QuestionCard question={s.questions[i]} />
        {evaluation.decision ? (
          <AgentDecision decision={evaluation.decision} followUpAdded={followUpNext} />
        ) : followUpNext && (
          <div className="note warn" role="status">
            ↳ <b>Follow-up added.</b> {nextQuestion.reason || 'The next question follows up on this answer.'}
          </div>
        )}
        {evaluation.replaced && (
          <div className="note" role="status">The difficulty of an upcoming question was adjusted to your answers so far.</div>
        )}
        <Feedback evaluation={evaluation} />
        <InlineMessage variant="box" message={error} />
        <Reveal className="end row" delay={0.9} y={10}>
          <Button variant="primary" disabled={finishing} onClick={next}>
            {finishing ? 'Calculating results…' : isLast ? 'Finish & view results →' : followUpNext ? 'Answer follow-up →' : 'Next Question →'}
          </Button>
        </Reveal>
      </div>
    </div>
  );
}
