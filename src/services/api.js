/**
 * API service layer.
 *
 * Every function currently returns mock/demo data after a short delay so the UI
 * can show realistic loading states. Each one is marked with a TODO showing where
 * the real HTTP call will go once the backend exists. Components must only talk
 * to the backend through this object (`api.xyz()`), so swapping implementations
 * does not require UI changes.
 *
 * The endpoint comments are placeholders carried over from the prototype, not a
 * finalised contract.
 */
import { INTERVIEW_HISTORY, SKILLS } from '../data/mockData';
import { buildCompletedResults, buildQuestions, buildResults, makeEvaluation, scoreAnswer } from './mockEngine';
import { sleep } from '../utils/format';

// TODO(backend): read the base URL from import.meta.env.VITE_API_BASE_URL (see .env.example).

export const api = {
  /** Uploads a CV and reports progress (0–100) through `onProgress`. */
  async uploadCV(file, onProgress) {
    // TODO(backend): send the file as multipart/form-data and parse PDF/DOCX server side.
    for (let p = 10; p <= 100; p += 10) {
      onProgress(p);
      await sleep(160);
    }
    return { id: 'cv_001', name: file.name };
  },

  /** Creates an interview session and its CV-aware questions. */
  async startInterview(config) {
    // TODO(backend): create the session from { cvId, role, type, difficulty, n } and return generated questions.
    await sleep(1400);
    return { id: `s_${Date.now()}`, questions: buildQuestions(config) };
  },

  /** Stores the candidate's answer for one question. */
  async submitAnswer(sessionId, questionIndex, answer) {
    // TODO(backend): persist the answer for this session and question.
    void sessionId; void questionIndex; void answer;
    await sleep(300);
    return { ok: true };
  },

  /** Returns the AI evaluation of one answer. */
  async getEvaluation(sessionId, question, answer) {
    // TODO(backend): fetch semantic scoring + generated feedback for this answer.
    void sessionId;
    await sleep(1900);
    return makeEvaluation(scoreAnswer(answer), question.type, answer);
  },

  /** Closes a session and returns its aggregated results. */
  async completeInterview({ session, config, items }) {
    // TODO(backend): mark the session complete and return the stored summary.
    await sleep(500);
    return buildCompletedResults({ session, config, items });
  },

  /** Returns full results (per-question evaluations) for a past interview. */
  async getInterviewResults(meta) {
    // TODO(backend): fetch the stored results for meta.id.
    await sleep(800);
    return buildResults(meta);
  },

  async getInterviewHistory() {
    // TODO(backend): fetch the signed-in user's interviews.
    await sleep(700);
    return INTERVIEW_HISTORY;
  },

  async getSkills() {
    // TODO(backend): fetch aggregated skill scores across sessions.
    await sleep(500);
    return SKILLS;
  },

  async updateProfile(profile) {
    // TODO(backend): persist profile changes.
    await sleep(300);
    return profile;
  },
};

export default api;
