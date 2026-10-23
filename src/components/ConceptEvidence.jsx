import Card from './Card';
import Chip from './Chip';

const STATUS = {
  demonstrated: { label: 'Explained', tone: 'ok' },
  partial: { label: 'Partly explained', tone: 'blue' },
  mentioned: { label: 'Named only', tone: 'warn' },
  missing: { label: 'Not found', tone: 'muted' },
};
const ORDER = ['demonstrated', 'partial', 'mentioned', 'missing'];

const LEVEL_NOTE = {
  limited: 'This answer gave limited evidence (short, or mostly a list of terms), so the scores could change with a fuller explanation.',
  insufficient: 'There was too little relevant content to judge this answer. Treat low scores as “not shown yet”, not as a lack of skill.',
};

/** What the evaluation is based on: each rubric concept with the sentence that supports it, and flagged claims. */
export default function ConceptEvidence({ evaluation }) {
  const concepts = [...(evaluation.concepts ?? [])].sort((a, b) => ORDER.indexOf(a.status) - ORDER.indexOf(b.status));
  const incorrect = evaluation.incorrect ?? [];
  const unsupported = evaluation.unsupported ?? [];
  if (!concepts.length && !incorrect.length && !unsupported.length && !LEVEL_NOTE[evaluation.evidenceLevel]) return null;

  return (
    <Card className="g" style={{ gap: 12 }}>
      <h3>Evidence behind the scores</h3>
      {LEVEL_NOTE[evaluation.evidenceLevel] && <div className="note warn" role="note">{LEVEL_NOTE[evaluation.evidenceLevel]}</div>}
      {concepts.length > 0 && (
        <ul className="evidence-list" aria-label="Key concepts">
          {concepts.map((c) => (
            <li key={c.concept}>
              <div className="row" style={{ gap: 8 }}>
                <Chip tone={STATUS[c.status]?.tone ?? 'muted'}>{STATUS[c.status]?.label ?? c.status}</Chip>
                <b>{c.concept}</b>
                {c.source === 'llm' && <span className="src">model review</span>}
              </div>
              {c.evidence && c.status !== 'missing' && <q className="quote">{c.evidence}</q>}
            </li>
          ))}
        </ul>
      )}
      {incorrect.length > 0 && (
        <div>
          <h4 className="mb-sm">Statements to check</h4>
          {incorrect.map((c, i) => (
            <div key={i} className="entry">
              {c.evidence && <q className="quote">{c.evidence}</q>}
              <p className="mt-sm" style={{ fontSize: '0.92rem' }}>{c.explanation}</p>
            </div>
          ))}
        </div>
      )}
      {unsupported.length > 0 && (
        <div>
          <h4 className="mb-sm">Claims without support</h4>
          {unsupported.map((c) => <q key={c} className="quote block">{c}</q>)}
          <p className="dim-note">A reason or an example would turn these into evidence.</p>
        </div>
      )}
    </Card>
  );
}
