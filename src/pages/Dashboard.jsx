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
  const { history, skills, user, loadError } = useApp();
  const openResults = useOpenResults();

  if (!history || !skills) return <div className="wrap"><Skeleton n={4} /></div>;

  const hasHistory = history.length > 0;
  const average = avg(history.map((h) => h.score));
  const { strongest, weakest } = rankSkills(skills);
  const stats = [
    { label: 'Average score', icon: '📊', value: average, suffix: '%' },
    { label: 'Interviews completed', icon: '✅', value: history.length },
    { label: 'Strongest area', icon: '💪', text: strongest ?? '—' },
    { label: 'Needs improvement', icon: '🎯', text: weakest ?? '—' },
  ];

  return (
    <Stagger className="wrap" gap={0.08}>
      <Card className="row sp welcome">
        <div>
          <h2>
            {hasHistory ? 'Welcome back' : 'Welcome'}, {getFirstName(user?.name ?? '')}{' '}
            <motion.span className="wave" aria-hidden="true" animate={{ rotate: [0, 16, -8, 16, 0] }} transition={{ delay: 0.9, duration: 1.1 }}>👋</motion.span>
          </h2>
          <p>{hasHistory ? `Your average score is ${average}%. Ready for another round?` : 'Upload your CV and complete your first practice interview to see your progress here.'}</p>
        </div>
        <div className="row">
          <Button to="/profile/review">Review CV profile</Button>
          <Button to="/cv-upload">＋ Start New Interview</Button>
        </div>
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
          {loadError && <p className="err">{loadError}</p>}
          {!hasHistory && (
            <div className="empty">
              <div className="big" aria-hidden="true">🗂️</div>
              <p className="mut">No completed interviews yet.</p>
              <Button variant="primary" className="mt-md" to="/cv-upload">Start your first interview</Button>
            </div>
          )}
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
          {Object.keys(skills).length === 0 && <p className="mut">Your skill scores appear after your first completed interview.</p>}
          {Object.entries(skills).slice(0, 4).map(([name, value], i) => (
            <ProgressBar key={name} label={name} value={value} delay={0.4 + i * 0.1} />
          ))}
          <Button to="/performance">Full performance →</Button>
          {hasHistory && <Button to="/plan">Your improvement plan →</Button>}
        </Card>
      </div>
    </Stagger>
  );
}
