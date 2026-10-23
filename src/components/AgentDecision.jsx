import Chip from './Chip';

const ACTION = {
  continue: 'Moving on',
  clarify: 'Asking you to expand',
  request_example: 'Asking for an example',
  probe_concept: 'Probing a concept',
  deepen: 'Going deeper',
};

/** Why the adaptive interview did (or did not) add a follow-up after this answer. */
export default function AgentDecision({ decision, followUpAdded }) {
  if (!decision) return null;
  const sourceLabel = decision.source === 'llm' ? 'AI model, checked by the app’s rules' : 'Rule-based';
  return (
    <div className={`note ${followUpAdded ? 'warn' : ''}`} role="status" aria-label="How the interview adapts">
      <div className="row" style={{ gap: 8 }}>
        <b>{followUpAdded ? '↳ Follow-up added' : 'Interview adapts'}:</b>
        <span>{ACTION[decision.action] ?? decision.action}</span>
        <Chip tone="muted">{sourceLabel}</Chip>
      </div>
      <p className="mt-sm" style={{ fontSize: '0.92rem' }}>{decision.rationale}</p>
      {decision.evidence?.length > 0 && (
        <ul className="dim-note" style={{ margin: '4px 0 0 18px' }}>
          {decision.evidence.map((e) => <li key={e}>{e}</li>)}
        </ul>
      )}
    </div>
  );
}
