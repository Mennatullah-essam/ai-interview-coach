/**
 * API service layer — the only place the frontend talks to the backend.
 *
 * Components keep calling `api.xyz()` and receive the same shapes they always
 * used (API_SPECIFICATION.md §17.3); the translation happens here.
 *
 * Authentication:
 * - The access token (short-lived JWT) lives only in memory, never in
 *   localStorage, and is sent as `Authorization: Bearer …`.
 * - The refresh token is an HttpOnly cookie the browser sends to /api/v1/auth
 *   automatically; JavaScript cannot read it. `restoreSession()` uses it on page
 *   load, so a reload keeps the user signed in.
 * - If a request returns 401, the client refreshes once and retries. If that
 *   fails, the registered `onSessionExpired` handler signs the user out.
 */

const BASE_URL = `${(import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')}/api/v1`;
const TIMEOUT_MS = 30000;
const CLIENT_HEADER = { 'X-AIC-Client': 'web' };

/** Error with the backend's machine-readable code and a user-safe message. */
export class ApiError extends Error {
  constructor({ status = 0, code = 'NETWORK_ERROR', message, details = [], retryable = false } = {}) {
    super(message || 'Could not reach the server. Check your connection and try again.');
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
    this.retryable = retryable;
  }
}

/** The message to show for any error thrown by this module. */
export const errorMessage = (error, fallback = 'Something went wrong. Please try again.') =>
  (error instanceof ApiError && error.message) || fallback;

let accessToken = null;
let refreshInFlight = null;
let onSessionExpired = () => {};

export function setSessionExpiredHandler(handler) {
  onSessionExpired = handler;
}

async function parseError(response) {
  try {
    const body = await response.json();
    if (body?.error) return new ApiError({ status: response.status, ...body.error });
  } catch { /* not JSON */ }
  return new ApiError({ status: response.status, code: 'HTTP_ERROR', message: 'Something went wrong. Please try again.' });
}

async function rawFetch(path, { method = 'GET', body, auth = true, headers = {} } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const finalHeaders = { ...headers };
  if (body !== undefined) finalHeaders['Content-Type'] = 'application/json';
  if (auth && accessToken) finalHeaders.Authorization = `Bearer ${accessToken}`;
  try {
    return await fetch(`${BASE_URL}${path}`, {
      method,
      headers: finalHeaders,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: 'include',
      signal: controller.signal,
    });
  } catch (e) {
    if (e.name === 'AbortError') throw new ApiError({ code: 'TIMEOUT', message: 'The server took too long to respond. Please try again.', retryable: true });
    throw new ApiError();
  } finally {
    clearTimeout(timer);
  }
}

/** Calls /auth/refresh once even if several requests need it at the same time. */
function refreshAccessToken() {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const response = await rawFetch('/auth/refresh', { method: 'POST', auth: false, headers: CLIENT_HEADER });
      if (!response.ok) {
        accessToken = null;
        return null;
      }
      const data = await response.json();
      accessToken = data.access_token;
      return data;
    })().finally(() => { refreshInFlight = null; });
  }
  return refreshInFlight;
}

async function request(path, options = {}) {
  let response = await rawFetch(path, options);
  if (response.status === 401 && options.auth !== false) {
    const refreshed = await refreshAccessToken().catch(() => null);
    if (!refreshed) {
      onSessionExpired();
      throw await parseError(response);
    }
    response = await rawFetch(path, options);
  }
  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return null;
  return response.json();
}

// --- adapters: API shapes → the shapes the UI already uses (§17.3) -------------------

const capitalize = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
const toApiEnum = (s) => (s ? s.toLowerCase() : s);
const formatDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '';
const formatSize = (bytes) => `${Math.round(bytes / 1024)} KB`;

const toUser = (u) => ({ id: u.id, name: u.name, email: u.email });

const toCvFile = (cv) => ({ id: cv.id, name: cv.original_filename, ext: cv.extension.toUpperCase(), size: formatSize(cv.size_bytes) });

const toQuestion = (q) => ({
  id: q.id,
  position: q.position,
  text: q.text,
  type: capitalize(q.type),
  category: q.category ?? null, // core | cv_skill | project | skill_gap | behavioral | follow_up
  reason: q.reason ?? '',
  focusSkills: q.focus_skills ?? [],
  parentId: q.parent_question_id ?? null,
  followUpKind: q.follow_up_kind ?? null,
});

/** Evaluation → { score, cats, strengths, weaknesses, tip, ideal }. "Structure" replaces "Confidence" (spec D5). */
const toEvaluation = (e) => ({
  score: e.overall_score,
  cats: {
    Relevance: e.category_scores.relevance,
    Clarity: e.category_scores.clarity,
    'Technical Depth': e.category_scores.technical_depth,
    Structure: e.category_scores.structure,
  },
  strengths: e.strengths,
  weaknesses: e.weaknesses,
  tip: e.improvement_tip,
  ideal: e.ideal_answer,
  // Milestone 4: rubric dimensions and explainable feedback (older evaluations have fewer fields).
  dimensions: (e.dimensions ?? []).map((d) => ({ key: d.key, label: d.label, score: d.score, weight: d.weight, explanation: d.explanation })),
  missing: e.missing_concepts ?? [],
  suggestions: e.suggestions ?? [],
  outline: e.ideal_outline ?? [],
  explanation: e.explanation ?? '',
  followUp: e.follow_up ? toQuestion(e.follow_up) : null,
  replaced: e.replaced_question ? toQuestion(e.replaced_question) : null,
  // Milestone 5: the evidence behind the scores and the interview agent's decision.
  concepts: (e.concept_evidence ?? []).map((c) => ({ concept: c.concept, status: c.status, evidence: c.evidence, source: c.source })),
  unsupported: e.unsupported_claims ?? [],
  incorrect: e.incorrect_claims ?? [],
  evidenceLevel: e.evidence_level ?? null,
  feedbackSource: e.feedback_source,
  decision: e.agent_decision
    ? { action: e.agent_decision.action, rationale: e.agent_decision.rationale, evidence: e.agent_decision.evidence ?? [],
        source: e.agent_decision.source, concept: e.agent_decision.target_concept, policy: e.agent_decision.policy }
    : null,
});

const toInterviewConfig = (c) => ({
  adaptive: Boolean(c?.adaptive),
  maxFollowUps: c?.max_follow_ups ?? 0,
  personalized: Boolean(c?.personalized),
  hasJobDescription: Boolean(c?.has_job_description),
});

/** Candidate profile as stored (fields keep their provenance: extracted | inferred | user). */
const toCandidateProfile = (p) => ({
  id: p.id,
  status: p.status, // draft | confirmed
  cvId: p.cv_id,
  profile: p.profile,
  confirmedAt: p.confirmed_at,
  updatedAt: p.updated_at,
});

const toPlan = (p) => ({ id: p.id, interviewId: p.interview_id, role: p.target_role, updatedAt: p.updated_at, ...p.plan });

/** Resolves null instead of throwing for an expected "not there yet" error code. */
const orNull = (code) => (error) => {
  if (error instanceof ApiError && error.code === code) return null;
  throw error;
};

const toMeta = (i) => ({
  id: i.id,
  date: formatDate(i.completed_at),
  role: i.target_role,
  type: capitalize(i.interview_type),
  diff: capitalize(i.difficulty),
  n: i.question_count,
  score: i.overall_score,
  status: capitalize(i.status),
});

const toResults = (r) => ({
  meta: toMeta(r.interview),
  items: r.items.map((item) => ({ q: toQuestion({ ...item.question, position: item.position }), ev: toEvaluation(item.evaluation) })),
  breakdown: {
    Structure: r.breakdown.structure,
    Relevance: r.breakdown.relevance,
    Clarity: r.breakdown.clarity,
    'Technical Knowledge': r.breakdown.technical_depth,
    Communication: r.breakdown.communication,
  },
  extraStrength: r.additional_strength,
  extraImprovement: r.additional_improvement,
  recommendations: r.recommendations,
});

function storeAuth(data) {
  accessToken = data.access_token;
  return toUser(data.user);
}

/** Multipart upload with real progress events (fetch has none, spec F14). */
function uploadWithProgress(file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${BASE_URL}/cvs`);
    xhr.withCredentials = true;
    xhr.timeout = 120000;
    if (accessToken) xhr.setRequestHeader('Authorization', `Bearer ${accessToken}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(Math.max(1, Math.min(95, Math.round((e.loaded / e.total) * 95))));
    };
    xhr.onload = () => {
      let body = null;
      try { body = JSON.parse(xhr.responseText); } catch { /* ignore */ }
      if (xhr.status >= 200 && xhr.status < 300) return resolve({ status: xhr.status, body });
      resolve({ status: xhr.status, body, error: body?.error ? new ApiError({ status: xhr.status, ...body.error }) : new ApiError({ status: xhr.status, code: 'HTTP_ERROR', message: 'Upload failed. Please try again.' }) });
    };
    xhr.onerror = () => reject(new ApiError());
    xhr.ontimeout = () => reject(new ApiError({ code: 'TIMEOUT', message: 'The upload took too long. Please try again.', retryable: true }));
    const form = new FormData();
    form.append('file', file);
    xhr.send(form);
  });
}

export const api = {
  // --- authentication ---------------------------------------------------------------
  async register({ name, email, password }) {
    return storeAuth(await request('/auth/register', { method: 'POST', body: { name, email, password }, auth: false }));
  },

  async login({ email, password }) {
    return storeAuth(await request('/auth/login', { method: 'POST', body: { email, password }, auth: false }));
  },

  /** Uses the HttpOnly refresh cookie to sign the user back in after a page reload. Resolves null if not signed in. */
  async restoreSession() {
    const data = await refreshAccessToken();
    return data ? toUser(data.user) : null;
  },

  async logout() {
    try {
      await rawFetch('/auth/logout', { method: 'POST', auth: false, headers: CLIENT_HEADER });
    } finally {
      accessToken = null;
    }
  },

  // --- profile --------------------------------------------------------------------------
  async getMe() {
    return toUser(await request('/users/me'));
  },

  async updateProfile(profile) {
    return toUser(await request('/users/me', { method: 'PATCH', body: { name: profile.name, email: profile.email } }));
  },

  /** Deletes the signed-in user's CVs and interviews (the account stays). */
  async clearMyData() {
    return request('/users/me/data', { method: 'DELETE' });
  },

  // --- CVs --------------------------------------------------------------------------------
  /** Uploads a CV and reports progress (0–100) through `onProgress`. Resolves the stored CV in UI shape. */
  async uploadCV(file, onProgress) {
    let result = await uploadWithProgress(file, onProgress);
    if (result.status === 401 && (await refreshAccessToken().catch(() => null))) {
      result = await uploadWithProgress(file, onProgress);
    }
    if (result.status === 401) onSessionExpired();
    if (result.error) throw result.error;
    onProgress?.(100);
    return toCvFile(result.body.cv);
  },

  /** The newest CV, so the upload step survives a page reload. */
  async getLatestCV() {
    const page = await request('/cvs?limit=1');
    return page.items.length ? toCvFile(page.items[0]) : null;
  },

  async deleteCV(cvId) {
    await request(`/cvs/${cvId}`, { method: 'DELETE' });
  },

  // --- interviews --------------------------------------------------------------------------
  /** Creates an interview with all of its questions. `config = {role, type, diff, n}`. */
  async startInterview(config, cvId) {
    const data = await request('/interviews', {
      method: 'POST',
      body: {
        cv_id: cvId,
        target_role: config.role,
        interview_type: toApiEnum(config.type),
        difficulty: toApiEnum(config.diff),
        question_count: config.n,
        job_description: config.jobDescription?.trim() || null,
        adaptive: Boolean(config.adaptive),
      },
    });
    return { id: data.id, questions: data.questions.map(toQuestion), server: toInterviewConfig(data.config) };
  },

  /** Stores the answer for one question (by its stable id). */
  async submitAnswer(sessionId, questionId, answer) {
    await request(`/interviews/${sessionId}/questions/${questionId}/answer`, { method: 'PUT', body: { answer_text: answer } });
    return { ok: true };
  },

  /** Scores the stored answer on the server and returns the evaluation in UI shape. */
  async getEvaluation(sessionId, question) {
    return toEvaluation(await request(`/interviews/${sessionId}/questions/${question.id}/evaluation`, { method: 'POST' }));
  },

  /** Marks an interview as abandoned when the user exits. */
  async abandonInterview(sessionId) {
    await request(`/interviews/${sessionId}/abandon`, { method: 'POST' });
  },

  /** Finishes the interview. The server aggregates its own stored scores (nothing is sent). */
  async completeInterview({ session }) {
    return toResults(await request(`/interviews/${session.id}/complete`, { method: 'POST' }));
  },

  /** Full results for a past interview. */
  async getInterviewResults(meta) {
    return toResults(await request(`/interviews/${meta.id}/results`));
  },

  /** Completed interviews, newest first (may be empty). */
  async getInterviewHistory() {
    const page = await request('/interviews?status=completed&limit=100');
    return page.items.map(toMeta);
  },

  // --- candidate profile (Milestone 4) ----------------------------------------------------
  /** The structured profile built from the newest CV, or null if no CV was uploaded yet. */
  async getCandidateProfile() {
    return request('/profile').then(toCandidateProfile, orNull('PROFILE_NOT_FOUND'));
  },

  /** Saves the reviewed profile. With `confirm` it starts personalising interviews. */
  async saveCandidateProfile(profile, confirm) {
    return toCandidateProfile(await request('/profile', { method: 'PUT', body: { profile, confirm } }));
  },

  /** Re-extracts from the newest CV, keeping items the user added. */
  async rebuildCandidateProfile() {
    return toCandidateProfile(await request('/profile/rebuild', { method: 'POST' }));
  },

  // --- improvement plans (Milestone 4) -------------------------------------------------------
  async getImprovementPlan(interviewId) {
    return toPlan(await request(`/interviews/${interviewId}/improvement-plan`));
  },

  /** The plan for the most recent completed interview, or null if there is none yet. */
  async getLatestImprovementPlan() {
    return request('/improvement-plans/latest').then(toPlan, orNull('PLAN_NOT_FOUND'));
  },

  /** Which intelligence is active on the server (embeddings, optional LLM). Never fails: null if unknown. */
  async getIntelligenceStatus() {
    try {
      const response = await rawFetch('/health', { auth: false });
      const body = await response.json();
      return body.intelligence ?? null;
    } catch {
      return null;
    }
  },

  /** Skill scores as an ordered object { label: score } (may be empty). */
  async getSkills() {
    const data = await request('/performance/skills');
    return Object.fromEntries(data.skills.map((s) => [s.label, s.score]));
  },
};

export default api;
