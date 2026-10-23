import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import Button from '../components/Button';
import Card from '../components/Card';
import Chip from '../components/Chip';
import ProgressBar from '../components/ProgressBar';
import Skeleton from '../components/Skeleton';
import { Reveal, Stagger, StaggerItem, StaggerList } from '../components/Reveal';
import api, { ApiError } from '../services/api';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useMounted } from '../hooks/useMounted';

const STATUS = {
  gap: { text: 'Skill gap', tone: 'bad', hint: 'Weak in at least two answers.' },
  needs_evidence: { text: 'Needs more evidence', tone: 'warn', hint: 'One weaker answer is not enough to call it a gap.' },
  weak: { text: 'Weak', tone: 'bad' },
  not_demonstrated: { text: 'Not yet demonstrated', tone: 'muted', hint: 'Not in your profile and not assessed yet.' },
};
const PRIORITY_TONE = { high: 'bad', medium: 'warn', low: 'muted' };
const COMPETENCY_LABEL = { demonstrated: 'Demonstrated', developing: 'Developing', weak: 'Weak (2+ answers)', needs_evidence: 'Needs more evidence', unassessed: 'Not assessed yet' };
const COMPETENCY_TONE = { demonstrated: 'ok', developing: 'blue', weak: 'bad', needs_evidence: 'warn', unassessed: 'muted' };

function Delta({ value }) {
  if (value === 0) return <span className="mut">±0</span>;
  return <span className={`delta ${value > 0 ? 'up' : 'down'}`}>{value > 0 ? `+${value}` : value}</span>;
}

/** Personalised, evidence-based plan for one completed interview (or the latest one at /plan). */
export default function ImprovementPlan() {
  useDocumentTitle('Improvement plan');
  const { interviewId } = useParams();
  const mounted = useMounted();
  const [state, setState] = useState('loading'); // loading | none | ready | error
  const [plan, setPlan] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(() => {
    setState('loading');
    const request = interviewId ? api.getImprovementPlan(interviewId) : api.getLatestImprovementPlan();
    request
      .then((p) => {
        if (!mounted.current) return;
        setPlan(p);
        setState(p ? 'ready' : 'none');
      })
      .catch((e) => {
        if (!mounted.current) return;
        if (e instanceof ApiError && e.status === 404) return setState('none'); // expected: nothing to show
        console.error(e);
        setError(e instanceof ApiError ? e.message : '');
        setState('error');
      });
  }, [interviewId, mounted]);

  useEffect(() => { load(); }, [load]);

  if (state === 'loading') return <div className="wrap"><Skeleton n={5} /></div>;
  if (state === 'error') {
    return (
      <div className="wrap slim">
        <Card enter>
          <p>{error || "We couldn't load your improvement plan."}</p>
          <Button className="mt-md" onClick={load}>Try again</Button>
        </Card>
      </div>
    );
  }
  if (state === 'none') {
    return (
      <div className="wrap slim">
        <h2>Improvement plan</h2>
        <Card enter className="empty mt-lg">
          <div className="big" aria-hidden="true">🧭</div>
          <p className="mut">Complete an interview to get a personal improvement plan based on your answers.</p>
          <Button variant="primary" className="mt-md" to="/cv-upload">Start an interview</Button>
        </Card>
      </div>
    );
  }

  const { progress } = plan;

  return (
    <Stagger className="wrap" gap={0.08}>
      <Reveal>
        <div className="row sp">
          <h2>Improvement plan</h2>
          <div className="row">
            <Button to="/history">History</Button>
            <Button variant="primary" to="/cv-upload">Practise again</Button>
          </div>
        </div>
        <p className="mut lead">{plan.role} · {plan.summary}</p>
      </Reveal>

      {progress?.overall && (
        <Card tinted className="mb-md">
          <b>Progress since your previous interview:</b> overall {progress.overall.previous}% → {progress.overall.current}% (<Delta value={progress.overall.change} />)
          {progress.items?.length > 0 && (
            <div className="row mt-sm" style={{ gap: 14 }}>
              {progress.items.map((item) => <span key={item.name}>{item.name}: <Delta value={item.change} /></span>)}
            </div>
          )}
        </Card>
      )}

      <div className="main2 wide">
        <div className="g">
          <Card className="g">
            <h3>Next steps</h3>
            {plan.next_steps.length === 0 && <p className="mut">No urgent actions — keep practising to collect more evidence.</p>}
            {plan.next_steps.map((step) => (
              <div key={step.title} className={`step ${step.priority}`}>
                <div className="row" style={{ gap: 8 }}>
                  <b>{step.title}</b>
                  <Chip tone={PRIORITY_TONE[step.priority]}>{step.priority} priority</Chip>
                </div>
                <p className="mt-sm" style={{ fontSize: '0.95rem' }}>{step.detail}</p>
                <p className="dim-note">Why: {step.evidence}</p>
              </div>
            ))}
          </Card>

          <div className="g g2">
            <Card>
              <h3 className="mb-md">Strengths</h3>
              {plan.strengths.length === 0 && <p className="mut">No strengths confirmed yet (a strength needs an average of 75%+).</p>}
              <StaggerList className="l s">
                {plan.strengths.map((s) => (
                  <StaggerItem as="li" key={s.name}>
                    <b>{s.name}</b>{s.consistent && <span className="src">consistent</span>} — {s.evidence}
                  </StaggerItem>
                ))}
              </StaggerList>
            </Card>
            <Card>
              <h3 className="mb-md">Weaknesses</h3>
              {plan.weaknesses.length === 0 && <p className="mut">No weak skills found in this interview.</p>}
              <div className="g" style={{ gap: 10 }}>
                {plan.weaknesses.map((w) => (
                  <div key={w.name}>
                    <div className="row" style={{ gap: 8 }}><b>{w.name}</b><Chip tone={STATUS[w.status]?.tone} title={STATUS[w.status]?.hint}>{STATUS[w.status]?.text ?? w.status}</Chip></div>
                    <p className="dim-note">{w.evidence}</p>
                    {w.examples?.length > 0 && (
                      <ul className="dim-note" style={{ margin: '0 0 0 18px' }}>
                        {w.examples.map((e) => <li key={e.question}>{e.question} ({e.score}/100)</li>)}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          </div>

          {plan.competencies?.length > 0 && (
            <Card>
              <h3 className="mb-sm">Your competencies: CV versus interviews</h3>
              <p className="mut mb-sm" style={{ fontSize: '0.88rem' }}>
                “In profile” comes from your reviewed CV; the interview column only reflects answers you gave. A weak answer never removes a skill from your profile.
              </p>
              <div className="table-wrap">
                <table className="ctable">
                  <thead><tr><th>Skill</th><th>In profile</th><th>Interview evidence</th><th>Average</th></tr></thead>
                  <tbody>
                    {plan.competencies.map((c) => (
                      <tr key={c.name}>
                        <td>{c.name}{c.required && <span className="src">required</span>}</td>
                        <td>{c.in_profile ? 'Yes' : '—'}</td>
                        <td><Chip tone={COMPETENCY_TONE[c.interview_status] ?? 'muted'}>{COMPETENCY_LABEL[c.interview_status] ?? c.interview_status}</Chip></td>
                        <td>{c.average ?? '—'}{c.answers ? <span className="mut"> ({c.answers} answer{c.answers > 1 ? 's' : ''})</span> : ''}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {plan.patterns.length > 0 && (
            <Card>
              <h3 className="mb-md">Repeated patterns</h3>
              <StaggerList className="l w">
                {plan.patterns.map((p) => <StaggerItem as="li" key={p.dimension}>{p.message}</StaggerItem>)}
              </StaggerList>
            </Card>
          )}

          {plan.practice_questions.length > 0 && (
            <Card>
              <h3 className="mb-md">Practice questions</h3>
              <StaggerList className="l r">
                {plan.practice_questions.map((q) => (
                  <StaggerItem as="li" key={q.bank_question_id}>{q.text} <span className="mut">— {q.reason}</span></StaggerItem>
                ))}
              </StaggerList>
            </Card>
          )}
        </div>

        <div className="g">
          {plan.role_skills_to_practice.length > 0 && (
            <Card>
              <h3 className="mb-md">Role skills to practise</h3>
              <div className="g" style={{ gap: 8 }}>
                {plan.role_skills_to_practice.map((r) => (
                  <div key={r.skill} className="row sp">
                    <span>{r.skill} <span className="mut" style={{ fontSize: '0.85rem' }}>({r.required_by})</span></span>
                    <Chip tone={STATUS[r.status]?.tone} title={STATUS[r.status]?.hint}>{STATUS[r.status]?.text ?? r.status}</Chip>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {plan.scores?.length > 0 && (
            <Card className="g">
              <h3>Evidence from this interview</h3>
              {plan.scores.map((s, i) => <ProgressBar key={s.name} label={s.name} value={s.score} delay={0.2 + i * 0.05} />)}
            </Card>
          )}

          {plan.exercises?.length > 0 && (
            <Card>
              <h3 className="mb-md">Exercises</h3>
              <StaggerList className="l r">
                {plan.exercises.map((e) => <StaggerItem as="li" key={e.title}>{e.title} <span className="mut">— {e.reason}</span></StaggerItem>)}
              </StaggerList>
            </Card>
          )}

          {plan.insufficient_evidence?.length > 0 && (
            <Card>
              <h3 className="mb-sm">Not enough evidence yet</h3>
              <ul className="dim-note" style={{ margin: '0 0 0 18px' }}>
                {plan.insufficient_evidence.map((i) => <li key={i.name}><b>{i.name}</b>: {i.evidence}</li>)}
              </ul>
            </Card>
          )}

          {plan.resources.length > 0 && (
            <Card>
              <h3 className="mb-md">Resources</h3>
              <StaggerList className="l r">
                {plan.resources.map((r) => (
                  <StaggerItem as="li" key={`${r.skill}-${r.title}`}>
                    {r.url ? <a href={r.url} target="_blank" rel="noopener noreferrer">{r.title}</a> : r.title}
                    <span className="mut"> — {r.skill}</span>
                  </StaggerItem>
                ))}
              </StaggerList>
            </Card>
          )}

          <Card tinted>
            <h3 className="mb-sm">How this plan was made</h3>
            <ul style={{ margin: '0 0 0 18px', fontSize: '0.88rem', display: 'grid', gap: 4 }}>
              {plan.notes.map((n) => <li key={n}>{n}</li>)}
            </ul>
          </Card>
        </div>
      </div>
    </Stagger>
  );
}
