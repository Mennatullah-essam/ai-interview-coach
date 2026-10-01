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
        <h3>🧠 AI insight</h3>
        <p className="mt-sm">
          {strongest} is your strongest area. {weakest} is lagging — practice explaining model choices and trade-offs with concrete metrics.
        </p>
      </Card>
    </Stagger>
  );
}
