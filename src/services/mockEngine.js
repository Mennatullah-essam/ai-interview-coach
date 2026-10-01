/**
 * Deterministic mock "AI" used by the demo API. It generates questions and
 * evaluations locally. Delete this file once the backend provides them.
 */
import { EVAL_TEMPLATES, FOLLOW_UP_SUFFIX, QUESTION_BANK, RESULT_SUMMARY_COPY, SCORE_OFFSETS } from '../data/mockData';
import { avg, clamp } from '../utils/scoring';
import { formatDate } from '../utils/format';

export function buildQuestions({ type, n }) {
  const pool = QUESTION_BANK.filter((q) => type === 'Mixed' || q.type === type);
  return Array.from({ length: n }, (_, i) => {
    const base = pool[i % pool.length];
    return i < pool.length ? base : { ...base, text: base.text + FOLLOW_UP_SUFFIX };
  });
}

export function scoreAnswer(answer) {
  return clamp(62 + Math.min(answer.length / 14, 22) + (/\d/.test(answer) ? 7 : 0) + (/result|impact|improv/i.test(answer) ? 4 : 0));
}

export function makeEvaluation(score, questionType, answer = '') {
  const kind = questionType === 'Technical' ? 'Technical' : 'Behavioral';
  const weaknesses = EVAL_TEMPLATES.weaknesses.slice(0, score >= 90 ? 1 : score >= 80 ? 2 : 3);
  if (answer && answer.length < 200) weaknesses.unshift(EVAL_TEMPLATES.briefAnswerWeakness);
  return {
    score,
    cats: {
      Relevance: clamp(score + 4),
      Clarity: clamp(score - 3),
      'Technical Depth': clamp(score - 5),
      Confidence: clamp(score - 1),
    },
    strengths: EVAL_TEMPLATES.strengths[kind],
    weaknesses: weaknesses.slice(0, 3),
    tip: EVAL_TEMPLATES.tips[kind],
    ideal: EVAL_TEMPLATES.idealAnswers[kind],
  };
}

export function buildResults(meta) {
  const questions = buildQuestions(meta);
  return {
    meta,
    items: questions.map((q, i) => ({ q, ev: makeEvaluation(clamp(meta.score + SCORE_OFFSETS[i % 10]), q.type) })),
    ...RESULT_SUMMARY_COPY,
  };
}

export function buildCompletedResults({ session, config, items }) {
  const meta = {
    id: session.id,
    date: formatDate(),
    role: config.role,
    type: config.type,
    diff: config.diff,
    n: items.length,
    score: avg(items.map((x) => x.ev.score)),
    status: 'Completed',
  };
  return { meta, items, ...RESULT_SUMMARY_COPY };
}
