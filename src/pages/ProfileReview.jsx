import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import Button from '../components/Button';
import Card from '../components/Card';
import Chip from '../components/Chip';
import ConfirmModal from '../components/ConfirmModal';
import InlineMessage from '../components/InlineMessage';
import Skeleton from '../components/Skeleton';
import { Reveal, Stagger } from '../components/Reveal';
import { EXPERIENCE_LEVELS, ROLES } from '../data/constants';
import api, { errorMessage } from '../services/api';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useMounted } from '../hooks/useMounted';
import { useToast } from '../hooks/useToast';

const SOURCE_LABEL = { extracted: 'from CV', inferred: 'inferred', user: 'you' };
const SOURCE_TONE = { extracted: 'blue', inferred: 'warn', user: 'ok' };

/** Small "where did this come from" tag shown next to every item. */
function Source({ source, evidence }) {
  if (!source) return null;
  return <span className="src" title={evidence || undefined}>{SOURCE_LABEL[source] ?? source}</span>;
}

/** Editable list of skill chips with an "add" field. */
function SkillEditor({ id, title, hint, items, onChange, placeholder }) {
  const [value, setValue] = useState('');
  const add = () => {
    const name = value.trim();
    if (!name) return;
    if (!items.some((s) => s.name.toLowerCase() === name.toLowerCase())) onChange([...items, { name, source: 'user' }]);
    setValue('');
  };
  return (
    <section aria-labelledby={id}>
      <h3 id={id} className="mb-sm">{title}</h3>
      {hint && <p className="mut mb-sm" style={{ fontSize: '0.88rem' }}>{hint}</p>}
      <div className="row" style={{ gap: 8 }}>
        {items.length === 0 && <span className="mut">None yet.</span>}
        {items.map((s) => (
          <Chip key={s.name} tone={SOURCE_TONE[s.source]} title={s.evidence || undefined}>
            {s.name}<Source source={s.source} />
            <button type="button" className="chip-x" aria-label={`Remove ${s.name}`} onClick={() => onChange(items.filter((x) => x !== s))}>×</button>
          </Chip>
        ))}
      </div>
      <div className="row mt-sm" style={{ flexWrap: 'nowrap' }}>
        <input type="text" aria-label={`Add to ${title}`} placeholder={placeholder} value={value} maxLength={80}
          onChange={(e) => setValue(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add(); } }} />
        <Button onClick={add} disabled={!value.trim()}>Add</Button>
      </div>
    </section>
  );
}

/** Editable list of free-text items (education, achievements, interests). */
function TextListEditor({ id, title, items, onChange, placeholder }) {
  const [value, setValue] = useState('');
  const add = () => {
    const text = value.trim();
    if (!text) return;
    onChange([...items, { text, source: 'user' }]);
    setValue('');
  };
  return (
    <section aria-labelledby={id}>
      <h3 id={id} className="mb-sm">{title}</h3>
      {items.length === 0 && <p className="mut">None yet.</p>}
      {items.map((item, i) => (
        <div key={`${item.text}-${i}`} className="entry row sp" style={{ flexWrap: 'nowrap' }}>
          <span>{item.text}<Source source={item.source} evidence={item.evidence} /></span>
          <Button size="sm" aria-label={`Remove ${item.text}`} onClick={() => onChange(items.filter((_, j) => j !== i))}>Remove</Button>
        </div>
      ))}
      <div className="row mt-sm" style={{ flexWrap: 'nowrap' }}>
        <input type="text" aria-label={`Add to ${title}`} placeholder={placeholder} value={value} maxLength={300}
          onChange={(e) => setValue(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add(); } }} />
        <Button onClick={add} disabled={!value.trim()}>Add</Button>
      </div>
    </section>
  );
}

export default function ProfileReview() {
  useDocumentTitle('Review your profile');
  const navigate = useNavigate();
  const mounted = useMounted();
  const { say } = useToast();
  const [state, setState] = useState('loading'); // loading | none | ready | error
  const [record, setRecord] = useState(null);
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState('');
  const [error, setError] = useState('');
  const [confirmRebuild, setConfirmRebuild] = useState(false);
  const [newProject, setNewProject] = useState('');

  const load = useCallback(() => {
    setState('loading');
    api.getCandidateProfile()
      .then((p) => {
        if (!mounted.current) return;
        setRecord(p);
        setDraft(p?.profile ?? null);
        setState(p ? 'ready' : 'none');
      })
      .catch((e) => { console.error(e); if (mounted.current) setState('error'); });
  }, [mounted]);

  useEffect(() => { load(); }, [load]);

  if (state === 'loading') return <div className="wrap"><Skeleton n={5} /></div>;
  if (state === 'error') {
    return (
      <div className="wrap slim">
        <Card enter>
          <p>We couldn't load your profile.</p>
          <Button className="mt-md" onClick={load}>Try again</Button>
        </Card>
      </div>
    );
  }
  if (state === 'none') {
    return (
      <div className="wrap slim">
        <Card enter className="empty">
          <div className="big" aria-hidden="true">📄</div>
          <p className="mut">Upload your CV first. We'll extract a profile from it for you to review.</p>
          <Button variant="primary" className="mt-md" to="/cv-upload">Upload CV</Button>
        </Card>
      </div>
    );
  }

  const set = (key, value) => setDraft((d) => ({ ...d, [key]: value }));
  const setValue = (key, value) => setDraft((d) => ({ ...d, [key]: { ...d[key], value: value === '' ? null : value } }));

  const save = async (confirm) => {
    setError('');
    setSaving(confirm ? 'confirm' : 'draft');
    try {
      const saved = await api.saveCandidateProfile(draft, confirm);
      if (!mounted.current) return;
      setRecord(saved);
      setDraft(saved.profile);
      say(confirm ? 'Profile confirmed. Your next interview will be personalised.' : 'Draft saved');
      if (confirm) navigate('/interview/setup');
    } catch (e) {
      if (mounted.current) setError(errorMessage(e, 'Could not save your profile. Please check the fields and try again.'));
    } finally {
      if (mounted.current) setSaving('');
    }
  };

  const rebuild = async () => {
    setConfirmRebuild(false);
    setError('');
    setSaving('rebuild');
    try {
      const fresh = await api.rebuildCandidateProfile();
      if (!mounted.current) return;
      setRecord(fresh);
      setDraft(fresh.profile);
      say('Profile re-extracted from your CV');
    } catch (e) {
      if (mounted.current) setError(errorMessage(e, 'Could not re-extract your profile.'));
    } finally {
      if (mounted.current) setSaving('');
    }
  };

  const addProject = () => {
    const name = newProject.trim();
    if (!name) return;
    set('projects', [...draft.projects, { name, technologies: [], source: 'user' }]);
    setNewProject('');
  };

  const confirmed = record.status === 'confirmed';

  return (
    <Stagger className="wrap" gap={0.08}>
      <Reveal>
        <div className="row sp">
          <h2>Review your profile</h2>
          <Chip tone={confirmed ? 'ok' : 'warn'}>{confirmed ? '✓ Confirmed' : 'Draft — not used yet'}</Chip>
        </div>
        <p className="mut lead">
          We extracted this from your CV. Check it, fix anything wrong and confirm. Only a confirmed profile personalises your
          interviews. Tags show where each item came from: <b>from CV</b>, <b>inferred</b> (a rule's best guess, hover to see why) or <b>you</b>.
        </p>
      </Reveal>

      {draft.warnings?.length > 0 && (
        <div className="note warn mb-md" role="status">
          <b>Please check:</b>
          <ul style={{ margin: '6px 0 0 18px' }}>{draft.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
        </div>
      )}

      <div className="main2">
        <div className="g">
          <Card className="g" style={{ gap: 18 }}>
            <label className="field">Target role <Source source={draft.target_role.source} evidence={draft.target_role.evidence} />
              <input type="text" list="role-options" maxLength={100} value={draft.target_role.value ?? ''} placeholder="e.g. Backend Developer"
                onChange={(e) => setValue('target_role', e.target.value)} />
              <datalist id="role-options">{ROLES.map((r) => <option key={r} value={r} />)}</datalist>
            </label>
            {draft.target_role.evidence && <p className="dim-note" style={{ marginTop: -10 }}>{draft.target_role.evidence}</p>}
            <label className="field">Experience level <Source source={draft.experience_level.source} evidence={draft.experience_level.evidence} />
              <select value={draft.experience_level.value ?? ''} onChange={(e) => setValue('experience_level', e.target.value)}>
                <option value="">Not set</option>
                {EXPERIENCE_LEVELS.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
              </select>
            </label>
            {draft.experience_level.evidence && <p className="dim-note" style={{ marginTop: -10 }}>{draft.experience_level.evidence}</p>}
            {draft.years_experience.value !== null && draft.years_experience.value !== undefined && (
              <p className="mut" style={{ fontSize: '0.9rem' }}>
                About <b>{draft.years_experience.value}</b> year(s) of experience <Source source={draft.years_experience.source} evidence={draft.years_experience.evidence} />
              </p>
            )}
          </Card>

          <Card className="g" style={{ gap: 22 }}>
            <SkillEditor id="tech-h" title="Technical skills" items={draft.technical_skills} placeholder="Add a skill, e.g. Docker"
              hint="Names are normalised (e.g. “sklearn” becomes scikit-learn)." onChange={(v) => set('technical_skills', v)} />
            <SkillEditor id="soft-h" title="Soft skills" items={draft.soft_skills} placeholder="Add a soft skill, e.g. Teamwork"
              onChange={(v) => set('soft_skills', v)} />
            {draft.expertise_areas.length > 0 && (
              <section aria-labelledby="areas-h">
                <h3 id="areas-h" className="mb-sm">Areas of expertise</h3>
                <div className="row" style={{ gap: 8 }}>
                  {draft.expertise_areas.map((a) => <Chip key={a.name} tone="muted" title={a.evidence || undefined}>{a.name}<Source source={a.source} /></Chip>)}
                </div>
              </section>
            )}
          </Card>

          <Card className="g" style={{ gap: 12 }}>
            <h3 id="exp-h">Experience</h3>
            {draft.experience.length === 0 && <p className="mut">No experience entries found.</p>}
            {draft.experience.map((e, i) => (
              <div key={`${e.title}-${i}`} className="entry">
                <div className="row sp" style={{ flexWrap: 'nowrap', alignItems: 'flex-start' }}>
                  <div>
                    <b>{e.title}</b>{e.organization && <> · {e.organization}</>}<Source source={e.source} />
                    {e.period && <div className="mut" style={{ fontSize: '0.88rem' }}>{e.period}</div>}
                  </div>
                  <Button size="sm" aria-label={`Remove ${e.title}`} onClick={() => set('experience', draft.experience.filter((_, j) => j !== i))}>Remove</Button>
                </div>
                {e.responsibilities.length > 0 && (
                  <ul style={{ margin: '6px 0 0 18px', fontSize: '0.9rem' }}>{e.responsibilities.map((r) => <li key={r}>{r}</li>)}</ul>
                )}
              </div>
            ))}
          </Card>

          <Card className="g" style={{ gap: 12 }}>
            <h3>Projects</h3>
            <p className="mut" style={{ fontSize: '0.88rem' }}>Confirmed projects can be used for project questions in technical interviews.</p>
            {draft.projects.length === 0 && <p className="mut">No projects found.</p>}
            {draft.projects.map((p, i) => (
              <div key={`${p.name}-${i}`} className="entry">
                <div className="row sp" style={{ flexWrap: 'nowrap', alignItems: 'flex-start' }}>
                  <div>
                    <b>{p.name}</b><Source source={p.source} />
                    {p.description && <div className="mut" style={{ fontSize: '0.9rem' }}>{p.description}</div>}
                    {p.technologies.length > 0 && <div className="row mt-sm" style={{ gap: 6 }}>{p.technologies.map((t) => <Chip key={t} tone="muted">{t}</Chip>)}</div>}
                  </div>
                  <Button size="sm" aria-label={`Remove ${p.name}`} onClick={() => set('projects', draft.projects.filter((_, j) => j !== i))}>Remove</Button>
                </div>
              </div>
            ))}
            <div className="row" style={{ flexWrap: 'nowrap' }}>
              <input type="text" aria-label="Add a project" placeholder="Add a project name" value={newProject} maxLength={150}
                onChange={(e) => setNewProject(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addProject(); } }} />
              <Button onClick={addProject} disabled={!newProject.trim()}>Add</Button>
            </div>
          </Card>

          <Card className="g" style={{ gap: 22 }}>
            <TextListEditor id="edu-h" title="Education" items={draft.education} placeholder="e.g. B.Sc. Computer Science" onChange={(v) => set('education', v)} />
            <TextListEditor id="ach-h" title="Achievements" items={draft.achievements} placeholder="e.g. Won first place in a hackathon" onChange={(v) => set('achievements', v)} />
            <TextListEditor id="int-h" title="Career interests" items={draft.career_interests} placeholder="e.g. NLP and search" onChange={(v) => set('career_interests', v)} />
          </Card>
        </div>

        <Card as="aside" enter className="g summary" aria-label="Save your profile">
          <h3>Save</h3>
          <p className="mut" style={{ fontSize: '0.9rem' }}>
            We never add qualifications you did not list. Anything marked <b>inferred</b> is a guess you can change.
          </p>
          <InlineMessage message={error} />
          <Button variant="primary" disabled={Boolean(saving)} onClick={() => save(true)}>
            {saving === 'confirm' ? 'Saving…' : confirmed ? 'Save changes' : 'Confirm profile'}
          </Button>
          {!confirmed && (
            <Button disabled={Boolean(saving)} onClick={() => save(false)}>{saving === 'draft' ? 'Saving…' : 'Save draft'}</Button>
          )}
          <Button disabled={Boolean(saving)} onClick={() => setConfirmRebuild(true)}>{saving === 'rebuild' ? 'Re-extracting…' : 'Re-extract from CV'}</Button>
          <Button to="/interview/setup">Continue to interview setup →</Button>
        </Card>
      </div>

      <AnimatePresence>
        {confirmRebuild && (
          <ConfirmModal title="Re-extract your profile?" text="Your profile will be rebuilt from your newest CV. Items you added yourself are kept; other edits are replaced, and you will need to confirm it again." confirmLabel="Re-extract" onConfirm={rebuild} onCancel={() => setConfirmRebuild(false)} />
        )}
      </AnimatePresence>
    </Stagger>
  );
}
