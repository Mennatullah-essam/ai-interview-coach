import Button from '../components/Button';
import Card from '../components/Card';
import ProgressBar from '../components/ProgressBar';
import Skeleton from '../components/Skeleton';
import TrendChart from '../components/TrendChart';
import { Stagger } from '../components/Reveal';
import { useApp } from '../hooks/useApp';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { rankSkills } from '../utils/scoring';

export default function Performance() {
  useDocumentTitle('Performance');
  const { history, skills } = useApp();
  if (!history || !skills) return <div className="wrap"><Skeleton /></div>;

  if (history.length === 0) {
    return (
      <Stagger className="wrap" gap={0.1}>
        <h2>Performance</h2>
        <Card className="empty mt-lg">
          <div className="big" aria-hidden="true">📈</div>
          <p className="mut">Complete an interview to see your score trend and skills.</p>
          <Button variant="primary" className="mt-md" to="/cv-upload">Start an interview</Button>
        </Card>
      </Stagger>
    );
  }

  const trend = [...history].reverse().map((h) => ({ id: h.id, value: h.score, label: h.date.split(',')[0] }));
  const { strongest, weakest } = rankSkills(skills);

  return (
    <Stagger className="wrap" gap={0.1}>
      <h2>Performance</h2>
      <div className="g g2 mt-lg">
        <Card>
          <h3 className="mb-md">Score trend</h3>
          <TrendChart data={trend} />
        </Card>
        <Card className="g">
          <h3>Skills across all sessions</h3>
          {Object.entries(skills).map(([name, value], i) => <ProgressBar key={name} label={name} value={value} delay={0.3 + i * 0.1} />)}
        </Card>
      </div>
      <Card tinted className="mt-md">
        <h3>🧠 Insight</h3>
        <p className="mt-sm">
          {strongest} is your strongest area so far.{' '}
          {weakest && weakest !== strongest ? `${weakest} is your lowest area, so focus your next practice session there.` : ''}
        </p>
        <p className="mut mt-sm" style={{ fontSize: '0.85rem' }}>Scores are automated estimates for practice.</p>
        <Button className="mt-md" variant="primary" to="/plan">Open your improvement plan →</Button>
      </Card>
    </Stagger>
  );
}
