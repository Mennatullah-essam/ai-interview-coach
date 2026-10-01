import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../components/Button';
import Feedback from '../components/Feedback';
import InlineMessage from '../components/InlineMessage';
import InterviewProgress from '../components/InterviewProgress';
import QuestionCard from '../components/QuestionCard';
import { Reveal } from '../components/Reveal';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useInterview } from '../hooks/useInterview';
import { useMounted } from '../hooks/useMounted';

export default function Evaluation() {
  useDocumentTitle('Answer evaluation');
  const navigate = useNavigate();
  const mounted = useMounted();
  const { session, index, currentEval, advance, finish } = useInterview();
  const [finishing, setFinishing] = useState(false);
  const [error, setError] = useState('');

  // Keep the last valid data so the page can fade out cleanly after advancing/finishing.
  const retained = useRef(null);
  if (session && currentEval) retained.current = { session, index, evaluation: currentEval };
  if (!retained.current) return null; // EvaluationGuard redirects when needed
  const { session: s, index: i, evaluation } = retained.current;

  const total = s.questions.length;
  const isLast = i + 1 >= total;

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
    } catch {
      if (!mounted.current) return;
      setError('Could not load your results. Please try again.');
      setFinishing(false);
    }
  };

  return (
    <div className="wrap">
      <InterviewProgress current={i + 1} total={total} config={s.config} progress={((i + 1) / total) * 100} onExit={() => navigate('/dashboard')} />
      <div className="g">
        <QuestionCard question={s.questions[i]} />
        <Feedback evaluation={evaluation} />
        <InlineMessage variant="box" message={error} />
        <Reveal className="end row" delay={0.9} y={10}>
          <Button variant="primary" disabled={finishing} onClick={next}>
            {finishing ? 'Calculating results…' : isLast ? 'Finish & view results →' : 'Next Question →'}
          </Button>
        </Reveal>
      </div>
    </div>
  );
}
