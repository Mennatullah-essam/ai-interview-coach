export const clamp = (v) => Math.max(45, Math.min(97, Math.round(v)));

export const avg = (list) => (list.length ? Math.round(list.reduce((x, y) => x + y, 0) / list.length) : 0);

/** Maps a 0–100 score to a label and a chip tone class. */
export const scoreLabel = (s) => {
  if (s >= 88) return { text: 'Excellent', tone: 'ok' };
  if (s >= 78) return { text: 'Strong', tone: 'blue' };
  return { text: 'Needs Improvement', tone: 'warn' };
};

/** Strongest and weakest skill; both null for a user with no completed interviews. */
export function rankSkills(skills) {
  const sorted = Object.entries(skills ?? {}).sort((a, b) => b[1] - a[1]);
  if (!sorted.length) return { strongest: null, weakest: null };
  return { strongest: sorted[0][0], weakest: sorted[sorted.length - 1][0] };
}

/**
 * Fallback only: the server sends the authoritative breakdown with the results.
 * Mirrors the server formula (Communication = mean of Clarity and Structure).
 */
export function buildBreakdown(items) {
  const mean = (key) => avg(items.map((x) => x.ev.cats[key]));
  const breakdown = {
    Structure: mean('Structure'),
    Relevance: mean('Relevance'),
    Clarity: mean('Clarity'),
    'Technical Knowledge': mean('Technical Depth'),
  };
  breakdown.Communication = avg([breakdown.Clarity, breakdown.Structure]);
  return breakdown;
}
