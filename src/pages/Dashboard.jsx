import { motion } from 'framer-motion';
import Button from '../components/Button';
import Card from '../components/Card';
import Chip from '../components/Chip';
import CountUp from '../components/CountUp';
import PressableRow from '../components/PressableRow';
import ProgressBar from '../components/ProgressBar';
import Skeleton from '../components/Skeleton';
import { Stagger, StaggerList } from '../components/Reveal';
import { useApp } from '../hooks/useApp';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useOpenResults } from '../hooks/useOpenResults';
import { avg, rankSkills, scoreLabel } from '../utils/scoring';
import { getFirstName } from '../utils/format';

export default function Dashboard() {
  useDocumentTitle('Dashboard');
  const { history, skills, user } = useApp();
  const openResults = useOpenResults();

  if (!history || !skills) return <div className="wrap"><Skeleton n={4} /></div>;

  const average = avg(history.map((h) => h.score));
  const { strongest, weakest } = rankSkills(skills);
  const stats = [
    { label: 'Average confidence', icon: '📊', value: average, suffix: '%' },
    { label: 'Interviews completed', icon: '✅', value: history.length },
    { label: 'Strongest area', icon: '💪', text: strongest },
    { label: 'Needs improvement', icon: '🎯', text: weakest },
  ];

  return (
    <Stagger className="wrap" gap={0.08}>
      <Card className="row sp welcome">
        <div>
          <h2>
            Welcome back, {getFirstName(user.name)}{' '}
            <motion.span className="wave" aria-hidden="true" animate={{ rotate: [0, 16, -8, 16, 0] }} transition={{ delay: 0.9, duration: 1.1 }}>👋</motion.span>
          </h2>
          <p>Your average confidence score is {average}%. Ready for another round?</p>
        </div>
        <Button to="/cv-upload">＋ Start New Interview</Button>
      </Card>

      <div className="g g4 stats" style={{ margin: '18px 0' }}>
        {stats.map((s, i) => (
          <Card key={s.label} hover>
            <div style={{ fontSize: '1.4rem' }} aria-hidden="true">{s.icon}</div>
            <div className="stat-value">{s.text ?? <CountUp value={s.value} suffix={s.suffix} delay={0.3 + i * 0.08} />}</div>
            <div className="mut">{s.label}</div>
          </Card>
        ))}
      </div>

      <div className="main2 wide">
        <Card>
          <div className="row sp">
            <h3>Recent sessions</h3>
            <Button to="/history">View all</Button>
          </div>
          <StaggerList as="div" className="mt-sm" delay={0.25}>
            {history.slice(0, 3).map((h) => (
              <PressableRow key={h.id} className="tr compact" label={`Review ${h.role} interview from ${h.date}`} onActivate={() => openResults(h)}>
                <div>
                  <b>{h.role}</b>
                  <div className="mut">{h.date} · {h.type} · {h.n} questions</div>
                </div>
                <Chip tone={scoreLabel(h.score).tone}>{h.score}%</Chip>
              </PressableRow>
            ))}
          </StaggerList>
        </Card>

        <Card className="g">
          <h3>Skill snapshot</h3>
          {Object.entries(skills).slice(0, 4).map(([name, value], i) => (
            <ProgressBar key={name} label={name} value={value} delay={0.4 + i * 0.1} />
          ))}
          <Button to="/performance">Full performance →</Button>
        </Card>
      </div>
    </Stagger>
  );
}
