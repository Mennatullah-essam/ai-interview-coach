# AI Interview Coach — API Specification

| | |
| --- | --- |
| **Document status** | Draft v0.1 — **design only** |
| **Date** | October 8, 2026 |
| **Team** | Capstone Team 147 |
| **Sources of truth** | (1) `AI_Capstone_Project_Proposal_Team147.docx` for intended technical scope; (2) the React/Vite frontend (`ai-interview-coach` v0.1.0), in particular `src/services/api.js` and how the UI actually consumes it |
| **Implementation status** | **Nothing in this document is implemented.** There is no FastAPI code, no database, no AI model integration and no AWS resource. The frontend still runs on the mock service layer. Everything below is a specification. |

**How to read this document.** Statements are tagged by origin so the team can tell what is decided from what is proposed:

- **[Proposal]** — stated in the capstone proposal.
- **[Frontend]** — observed in the current React code.
- **[Recommended]** — a design choice made in this document to fill a gap; reversible and not mandated by the proposal.
- **[Open]** — genuinely unresolved; see [Section 23](#23-open-decisions--questions).

---

## Table of contents

1. [System Overview](#1-system-overview)
2. [Current Frontend Analysis](#2-current-frontend-analysis)
3. [Frontend → Backend Mapping](#3-frontend--backend-mapping)
4. [API Architecture](#4-api-architecture)
5. [Authentication](#5-authentication)
6. [CV API](#6-cv-api)
7. [Interview API](#7-interview-api)
8. [Question API](#8-question-api)
9. [Answer API](#9-answer-api)
10. [Evaluation API](#10-evaluation-api)
11. [Results API](#11-results-api)
12. [History API](#12-history-api)
13. [Performance API](#13-performance-api)
14. [Profile API](#14-profile-api)
15. [Database Models](#15-database-models)
16. [AI/ML Pipeline](#16-aiml-pipeline)
17. [Request/Response Schemas](#17-requestresponse-schemas)
18. [Error Handling](#18-error-handling)
19. [Security Requirements](#19-security-requirements)
20. [AWS Architecture](#20-aws-architecture)
21. [MVP Scope](#21-mvp-scope)
22. [Future Enhancements](#22-future-enhancements)
23. [Open Decisions / Questions](#23-open-decisions--questions)
24. [Frontend Integration Plan](#24-frontend-integration-plan)
- [Appendix A — Validation report](#appendix-a--validation-report)

---

## 1. System Overview

### 1.1 What the product is

AI Interview Coach helps job seekers and students prepare for interviews. A user uploads a CV, selects a target role, answers interview questions by text, and receives an AI-evaluated confidence score, strengths, weaknesses and improvement suggestions. With GenAI, the system can also produce personalized questions and ideal-answer suggestions. **[Proposal §2]**

### 1.2 Intended end-to-end workflow

**[Proposal §4]** describes four stages, which this specification maps to API calls:

| # | Proposal stage | Realised by |
| --- | --- | --- |
| 1 | **Input** — user uploads CV, selects target role, answers questions via text in React | `POST /cvs`, `POST /interviews`, `PUT …/answer` |
| 2 | **Processing / backend** — FastAPI receives requests; data stored in PostgreSQL/MySQL on AWS RDS | All endpoints; Section 15 |
| 3 | **AI execution** — Sentence Transformers / BERT / DistilBERT compute a confidence score and strengths/weaknesses; the GenAI layer (OpenAI API / Amazon Bedrock) generates personalized questions and ideal-answer suggestions | `POST /interviews` (questions), `POST …/evaluation` (scoring); Section 16 |
| 4 | **Output** — score, strengths, weaknesses and suggestions returned to React; CloudWatch monitors the system | `POST …/evaluation`, `GET …/results`; Section 20 |

### 1.3 Technology scope (from the proposal)

| Layer | Technology | Status |
| --- | --- | --- |
| Frontend | React.js (Vite, React Router, Framer Motion) | **[Proposal]** React.js; the rest is already built |
| Backend | Python, FastAPI | **[Proposal]** |
| Database | PostgreSQL **or** MySQL on AWS RDS | **[Proposal]** engine **[Open]** (OD-2) |
| Answer evaluation | Sentence Transformers, BERT / DistilBERT | **[Proposal]** |
| Speech-to-text | Whisper | **[Proposal]** (role and value-proposition text only; the written workflow is text-only) — **[Open]** (OD-6) |
| GenAI | OpenAI API **or** Amazon Bedrock — described as *"GenAI, optional"* | **[Proposal]** provider **[Open]** (OD-3); optionality shapes the MVP (Section 21) |
| RAG | Curated question banks and career resources "used for RAG"; track is "LLMs & RAG" | **[Proposal]** intent; mechanism **[Open]** (OD-5) |
| Infrastructure | AWS EC2, S3, RDS, API Gateway, CloudWatch | **[Proposal]** (listed in the Cloud/DevOps role) |
| Orchestration framework | "None specified yet" | **[Proposal]** — none assumed |

### 1.4 Team ownership (from the proposal's role table)

| Area | Owner |
| --- | --- |
| Cloud / DevOps (EC2, S3, RDS, API Gateway, CloudWatch) | Mennatullah Essam Mohamed Kamal Abdelfattah |
| Backend (FastAPI, endpoints) | Sawsan Mahmoud Elgamal |
| ML (Whisper, answer-evaluation models) | George Ehab Sobhy Dos |
| Database (schema for users, sessions, results) | Ahmed Hamdy Ahmed |
| Frontend (React UI) | Anas Hany Shaker |
| GenAI integration (OpenAI / Bedrock) | Belal Salah Hassan |

### 1.5 Scope boundaries of this document

In scope: the HTTP contract, data models, AI pipeline responsibilities, error and security requirements, AWS placement, MVP split, open decisions, and a frontend integration plan.

Out of scope: any implementation, model training, prompt text, infrastructure code, or UI redesign. The existing React frontend is **not modified** by this task.

---

## 2. Current Frontend Analysis

Method: the full `src/` tree was inspected, and `api.js` call sites were located with a text search (results in 2.4). Findings that affect the backend are numbered **F1–F25** and referenced throughout.

### 2.1 Routes and screens

| Route | Page | Data it needs | Guard |
| --- | --- | --- | --- |
| `/` | Landing | user first name (button "Sign in as {name}") | — |
| `/dashboard` | Dashboard | user, history, skills | — |
| `/cv-upload` | CV upload | CV file state | — |
| `/interview/setup` | Interview setup | CV (name), config | shows "upload CV first" if no CV |
| `/interview/session` | Answer a question | session (questions), index | needs session and unanswered question |
| `/interview/evaluation` | Feedback for one answer | session, index, evaluation | needs session and evaluation |
| `/results` | Interview results | results payload | needs results loaded/loading |
| `/history` | Interview history | history | — |
| `/performance` | Trends and skills | history, skills | — |
| `/profile` | Profile / reset | user | — |

### 2.2 Forms, inputs and validation actually enforced by the UI

| Form / input | Fields | Client-side rules (source of truth for server parity) |
| --- | --- | --- |
| CV upload | file | extension must be `pdf` or `docx` (checked by extension only); size ≤ 5 MB; hidden input `accept=".pdf,.docx"` |
| Interview setup | target role | one of 7 preset chips **or** free text; custom text must be ≥ 3 characters; **no maximum** |
| | interview type | `Technical` · `Behavioral` · `Mixed` |
| | difficulty | `Beginner` · `Intermediate` · `Advanced` |
| | question count | `5` · `10` · `15` |
| Answer | answer text | trimmed length ≥ 30; textarea `maxLength` 1500 |
| Profile | name, email | name trimmed ≥ 2; email must match `^\S+@\S+\.\S+$` |

Preset roles: AI Engineer, Machine Learning Engineer, Data Scientist, Software Engineer, Backend Developer, Frontend Developer, Data Analyst.

### 2.3 User actions

Upload / replace / remove CV · pick role, type, difficulty, count · start interview · type, clear and submit an answer · view evaluation (incl. expandable "stronger answer example") · next question / finish · exit interview (confirm) · open past results from dashboard or history · open per-question feedback modal · filter history by type · toggle theme (client-only) · save profile · reset demo data · sign out (navigation only).

### 2.4 Service functions (`src/services/api.js`) and their real call sites

Verified with a search for each function name across `src/`:

| Function (current signature) | Called from | What the caller does with the result |
| --- | --- | --- |
| `uploadCV(file, onProgress)` | `hooks/useCVUpload.js` | uses `res.id` only; name/size/extension are taken from the local `File`. `onProgress(0–100)` drives the progress bar |
| `startInterview(config)` where `config = {role, type, diff, n}` | `context/InterviewContext.jsx` | stores `{id, questions[{text,type}]}` as the session; **all questions must arrive in one response** |
| `submitAnswer(sessionId, questionIndex, answer)` | `context/InterviewContext.jsx` | awaited, result ignored |
| `getEvaluation(sessionId, question, answer)` | `context/InterviewContext.jsx` | awaited right after `submitAnswer`; result displayed on the Evaluation page |
| `completeInterview({session, config, items})` | `context/InterviewContext.jsx` | returns a results payload that is shown immediately and `meta` is prepended to history |
| `getInterviewResults(meta)` | `context/AppContext.jsx` | results for a past interview opened from the dashboard / history |
| `getInterviewHistory()` | `context/AppContext.jsx` | loaded once at app start; also drives dashboard stats and the Performance trend |
| `getSkills()` | `context/AppContext.jsx` | loaded once at app start |
| `updateProfile(profile)` | `pages/Profile.jsx` | replaces `user` in state with the returned object |

There is **no** function for: removing a CV, fetching the current user, signing in/out, abandoning an interview, or resetting data. (See F9–F12.)

### 2.5 Mock data currently returned (shapes the UI depends on)

**History / interview metadata (`meta`)**

```json
{ "id": "h4", "date": "Sep 24, 2026", "role": "AI Engineer", "type": "Technical",
  "diff": "Intermediate", "n": 10, "score": 84, "status": "Completed" }
```

**Question** — `{ "text": "...", "type": "Technical" | "Behavioral" }`

**Evaluation (`ev`)**

```json
{ "score": 82,
  "cats": { "Relevance": 86, "Clarity": 79, "Technical Depth": 77, "Confidence": 81 },
  "strengths": ["..."], "weaknesses": ["..."], "tip": "...", "ideal": "..." }
```

**Results payload**

```json
{ "meta": { }, "items": [ { "q": { }, "ev": { } } ],
  "extraStrength": "Relevant, practical examples",
  "extraImprovement": "Quantifying impact",
  "recommendations": ["...", "...", "..."] }
```

**Skills** — an object `{ Communication: 88, Relevance: 86, Confidence: 82, Clarity: 81, "Technical Depth": 76 }`.

**User** — `{ name, email }`. **Stored CV** — `{ name, ext, size, id }`.

### 2.6 Values the frontend currently computes itself

| Value | Where | Rule |
| --- | --- | --- |
| Dashboard "Average confidence" | `Dashboard.jsx` | `avg(history.score)` (rounded) |
| Dashboard "Interviews completed" | `Dashboard.jsx` | `history.length` |
| Strongest / weakest area | `utils/scoring.js` `rankSkills` | max / min of `skills` |
| Results "Performance breakdown" | `utils/scoring.js` `buildBreakdown` | mean per category over items; **Technical Knowledge = mean of "Technical Depth"; Communication = avg(Clarity, Confidence)** |
| Results strengths / improvements | `Results.jsx` | top-2 / bottom-2 of the breakdown, plus one server-supplied extra string each |
| Overall result label | `scoreLabel` | ≥ 88 Excellent · ≥ 78 Strong · else Needs Improvement |
| Estimated time | `InterviewSetup.jsx` | `n × 3` minutes |
| Performance trend | `Performance.jsx` | history reversed (oldest → newest), label = date text before the comma |

### 2.7 State passed between components

`AppContext`: `user, cvFile, config, history, skills, results, resultsStatus`. `InterviewContext`: `session {id, questions, config}, index, items[{q, ev}], currentEval, starting`. Theme and toast are client-only.

### 2.8 Findings that constrain the backend

| ID | Finding | Consequence for the API |
| --- | --- | --- |
| **F1** | `startInterview` receives `{role,type,diff,n}` only. The uploaded CV's `id` is stored in `cvFile.id` but **never sent**. | A real API must receive `cv_id`. Small frontend change required (FC-1). |
| **F2** | Questions are addressed by array index, and evaluation receives the whole question *text*. | Backend identifies questions by ID. Questions must be returned with IDs; the adapter keeps them in the session (FC-2). |
| **F3** | `getEvaluation` is called immediately after `submitAnswer` and is *computed* on request (mock waits ~1.9 s), not merely fetched. | Evaluation is a `POST` that triggers scoring (idempotent), not a `GET`. A `GET` is still useful for recovery. |
| **F4** | `completeInterview` sends every `{q, ev}` pair back from the client. | The server already holds all answers and evaluations; it must aggregate them itself and **ignore client-supplied scores** (trust boundary). |
| **F5** | Dates are display strings (`"Sep 24, 2026"`). `Performance.jsx` does `h.date.split(',')[0]`. | API returns ISO-8601 UTC. The adapter formats it, preserving the current strings (FC-5). |
| **F6** | History is assumed to be the **complete** list, newest first; dashboard stats and the trend are computed from it. | List endpoint is paginated, so aggregate stats should come from a summary endpoint (E21) or the full list must be fetched (cap noted in E19). |
| **F7** | `skills` is an object whose **key order matters** (`Object.entries(skills).slice(0,4)` on the dashboard). | API returns an ordered array, sorted by score descending; adapter rebuilds the object. |
| **F8** | Category naming differs: eval category *Technical Depth* ↔ results breakdown *Technical Knowledge*; *Communication* exists only as a derived value. | API uses stable keys (`technical_depth`, `communication`); server computes `communication` with the same formula so Results and Performance agree. |
| **F9** | Removing a CV only clears local state; no API call. CV state is lost on refresh. | Needs `DELETE /cvs/{id}` and `GET /cvs` (FC-3). |
| **F10** | No login, no registration, no token handling; user is seeded from `DEMO_USER`; "Sign out" only navigates. | Authentication cannot be supported by the current UI. Needs screens + token handling (FC-4). Method itself is **[Open]** (OD-1). |
| **F11** | Email is editable in Profile; "Reset demo data" clears CV/history. | With real accounts, email is an identity attribute; "reset demo data" has no direct production equivalent (OD-9). |
| **F12** | "Exit interview" performs no API call; refreshing the page loses the session. | Optional `abandon` endpoint (E13) and `GET /interviews/{id}` (E12) to enable cleanup and future resume. |
| **F13** | Error handling is generic (fixed strings per screen); no use of error codes, no 401 handling, no request timeout, no retry. | Spec defines machine-readable error codes (Section 18); frontend should map them (FC-6). |
| **F14** | Upload progress is a callback `onProgress(0–100)`. Browser `fetch` does not expose upload progress. | Adapter must use `XMLHttpRequest` (or an HTTP library that wraps it). |
| **F15** | Question counts of 5/10/15 are offered; the mock reuses its small pool with a "Follow-up" suffix for extras. | Real generation must produce *n* distinct questions. |
| **F16** | "Confidence" means two things: the dashboard label "Average confidence" (mean overall score) and a per-answer category. | Terminology to settle (OD-8); API keeps `overall_score` and `confidence` as separate fields. |
| **F17** | The user's own answer text is never displayed back (Results shows question + feedback only). | Answer text is stored and may be returned, but the UI does not need it for MVP. |
| **F18** | Custom role has a minimum length (3) but no maximum. | Server enforces a maximum (100 characters). |
| **F19** | File type is validated by extension only. | Server must validate content (magic bytes), not just name. |
| **F20** | No pagination anywhere. | See F6. |
| **F21** | The number of questions is fixed at creation. The proposal's "personalized follow-up questions" would add questions dynamically. | Dynamic follow-ups are **not supported** by the current UI; deferred (Section 22). |
| **F22** | Answers are text only. | Whisper/speech input is not supported by the UI; deferred (OD-6). |
| **F23** | No field for a job description, although the proposal lists job descriptions among input data. | Not in MVP (OD-7). |
| **F24** | History `status` is always `"Completed"`. | History endpoint returns completed interviews only by default. |
| **F25** | Enum values are display strings (`"Intermediate"`). | API uses lowercase enums (`intermediate`); adapter maps both ways. |
| **F26** | **Empty state is unsupported.** `rankSkills({})` throws a `TypeError` (`sorted[0][0]` on an empty list), so the Dashboard and Performance page break for a user with no completed interviews. The mock always has data, so this never showed. | Real new users have no history; E20/E21 return empty values. Frontend must handle it (FC-7). |

---

## 3. Frontend → Backend Mapping

### 3.1 Every existing service function

Endpoint IDs (`E01`…`E22`) refer to the catalog in [Section 4.4](#44-endpoint-catalog) and the detailed sections that follow.

| Frontend feature | Service function | Method & endpoint | Request | Response (fields the UI uses) | Database | AI / ML | Possible errors |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Upload CV | `uploadCV(file, onProgress)` | `POST /api/v1/cvs` **E07** | `multipart/form-data`, field `file` (PDF/DOCX, ≤ 5 MB) | `cv.id` (UI also shows name/ext/size, which come from the local file today); plus `extracted.skills` for later personalization | insert `cvs`, `cv_profiles`, `cv_skills`; file to S3 | text extraction (deterministic); structured extraction (method open, OD-4) | `UNSUPPORTED_FILE_TYPE`, `FILE_TOO_LARGE`, `CV_UNREADABLE`, `UNAUTHORIZED`, `DATABASE_UNAVAILABLE`, `STORAGE_UNAVAILABLE` |
| Start interview (generate questions) | `startInterview(config)` | `POST /api/v1/interviews` **E11** | JSON `{cv_id, target_role, interview_type, difficulty, question_count}` | `id`, `questions[{id, position, text, type}]`, echoed `config` | insert `interviews`, `interview_questions` | question retrieval / generation; ideal-answer generation (stored, hidden) | `CV_REQUIRED`, `CV_NOT_FOUND`, `INVALID_INTERVIEW_CONFIG`, `AI_SERVICE_UNAVAILABLE`, `AI_SERVICE_TIMEOUT` |
| Submit answer | `submitAnswer(sessionId, questionIndex, answer)` | `PUT /api/v1/interviews/{id}/questions/{qid}/answer` **E15** | JSON `{answer_text}` | `{id, question_id, submitted_at}` (UI ignores the body) | upsert `answers` | none | `ANSWER_EMPTY`, `ANSWER_TOO_SHORT`, `ANSWER_TOO_LONG`, `INTERVIEW_NOT_FOUND`, `QUESTION_NOT_FOUND`, `INTERVIEW_NOT_ACTIVE`, `ANSWER_ALREADY_EVALUATED` |
| Evaluate answer | `getEvaluation(sessionId, question, answer)` | `POST /api/v1/interviews/{id}/questions/{qid}/evaluation` **E16** | no body (answer already stored) | `overall_score`, `category_scores`, `strengths`, `weaknesses`, `improvement_tip`, `ideal_answer` | insert `evaluations` (idempotent) | semantic similarity + scoring (ML); feedback wording (rules and/or GenAI) | `ANSWER_NOT_FOUND`, `AI_SERVICE_UNAVAILABLE`, `AI_SERVICE_TIMEOUT`, `INTERVIEW_NOT_ACTIVE` |
| Finish interview | `completeInterview({session, config, items})` | `POST /api/v1/interviews/{id}/complete` **E14** | no body (client `items` are ignored, F4) | full results payload (same as E18) | insert `interview_results`; update `interviews`, `user_performance` | recommendations (rules and/or GenAI) | `INTERVIEW_INCOMPLETE`, `INTERVIEW_NOT_FOUND`, `INTERVIEW_NOT_ACTIVE`, `DATABASE_UNAVAILABLE` (a GenAI wording failure never fails this call; it falls back to rules) |
| Open past results | `getInterviewResults(meta)` | `GET /api/v1/interviews/{id}/results` **E18** | path `id = meta.id` | results payload | read `interview_results` + evaluations | none | `INTERVIEW_NOT_FOUND`, `RESULTS_NOT_AVAILABLE` |
| History list (+ dashboard recents) | `getInterviewHistory()` | `GET /api/v1/interviews?status=completed` **E19** | query: `status`, `type`, `limit`, `offset` | `items[{id, completed_at, target_role, interview_type, difficulty, question_count, overall_score, status}]` | read `interviews` | none | `UNAUTHORIZED` |
| Skills (dashboard snapshot + Performance) | `getSkills()` | `GET /api/v1/performance/skills` **E20** | — | ordered `skills[{key, label, score}]` | read `user_performance` | none | `UNAUTHORIZED` |
| Save profile | `updateProfile(profile)` | `PATCH /api/v1/users/me` **E06** | JSON `{name?, email?}` | updated user `{id, name, email}` | update `users` | none | `VALIDATION_ERROR`, `EMAIL_ALREADY_IN_USE`, `UNAUTHORIZED` |

### 3.2 UI capabilities that have **no** service function today

These exist in the UI (or are required by the proposal's workflow) but cannot reach a backend until a function is added. None of them are implemented; each is a frontend change listed in Section 24.

| Capability | Needed endpoint | Why it is missing today |
| --- | --- | --- |
| Remove / replace CV | `DELETE /cvs/{id}` **E10** | "Remove" only clears state (F9) |
| Restore CV after page refresh | `GET /cvs` **E08**, `GET /cvs/{id}` **E09** | CV lives in memory only (F9) |
| Load the signed-in user | `GET /users/me` **E05** | user seeded from `DEMO_USER` (F10) |
| Register / sign in / refresh / sign out | **E01–E04** | no auth UI (F10); method undecided (OD-1) |
| Abandon an interview on "Exit" | `POST /interviews/{id}/abandon` **E13** | Exit is navigation only (F12) |
| Resume / reload an interview | `GET /interviews/{id}` **E12**, `GET …/evaluation` **E17** | session lost on refresh (F12) |
| Dashboard stats without loading all history | `GET /performance/summary` **E21** | stats computed client-side (F6) |
| Liveness / readiness checks | `GET /health` **E22** | operational need, not UI |
| "Reset demo data" | none (see OD-9) | demo-only concept |

### 3.3 End-to-end contract flows

Each flow shows the exact hand-off: **React → HTTP → FastAPI → processing → HTTP → React**. Full field tables are in the endpoint sections.

#### Flow A — CV upload (`multipart/form-data`)

```
React (useCVUpload → api.uploadCV)
  │  validates ext ∈ {pdf, docx}, size ≤ 5 MB            (UX only; server re-validates)
  │  POST /api/v1/cvs
  │  Content-Type: multipart/form-data; boundary=…
  │  Authorization: Bearer <token>
  │  part "file": binary, filename="cv.pdf", Content-Type: application/pdf
  ▼
FastAPI
  │  1. authenticate                      4. extract text (deterministic)
  │  2. enforce size limit while reading  5. structured extraction → skills (OD-4)
  │  3. verify magic bytes + extension    6. store file in S3; insert cvs/cv_profiles/cv_skills
  ▼
HTTP 201 Created
  │  { "cv": { "id": "9d4e6a52-…", "original_filename": "cv.pdf", "extension": "pdf",
  │            "size_bytes": 124318, "parse_status": "parsed", "created_at": "…" },
  │    "extracted": { "skills": ["Python", "PyTorch", "FastAPI"], … } }
  ▼
React: adapter returns { id, name } → setFile({ name, ext, size, id })
       progress events come from XMLHttpRequest.upload.onprogress (F14)
```

Multipart contract: exactly one part named `file`. Other parts are rejected (`VALIDATION_ERROR`). The server never trusts the client-supplied `Content-Type` or filename (Section 19).

#### Flow B — Create interview (JSON)

```
React (InterviewSetup → InterviewContext.start → api.startInterview)
  │  POST /api/v1/interviews
  │  { "cv_id": "9d4e6a52-…", "target_role": "AI Engineer",
  │    "interview_type": "technical", "difficulty": "intermediate", "question_count": 10 }
  ▼
FastAPI
  │  validate body → load CV (owned by caller) → pick/generate N questions + ideal answers
  │  insert interviews + interview_questions (ideal answers stored, never returned here)
  ▼
HTTP 201 Created
  │  { "id": "b8f1c0de-…", "status": "in_progress", "config": { … },
  │    "questions": [ { "id": "0a7c5e31-…", "position": 1, "text": "…", "type": "technical" }, … ] }
  ▼
React: adapter → session { id, questions:[{id, text, type}], config } ; navigate /interview/session
```

#### Flow C — Submit answer, then evaluate

```
React (InterviewSession.submit → InterviewContext.submitAnswer)
  │  1) PUT  /api/v1/interviews/{iid}/questions/{qid}/answer     { "answer_text": "…" }
  │       FastAPI: validate length 30–1500 (after trim) → upsert answers → 200 { id, … }
  │  2) POST /api/v1/interviews/{iid}/questions/{qid}/evaluation (no body)
  │       FastAPI: load answer + stored ideal answer
  │                → ML: embed + cosine similarity → category scores → overall score
  │                → strengths / weaknesses / tip (rules and/or GenAI)
  │                → insert evaluations → 201 { evaluation }
  ▼
React: adapter → { score, cats, strengths, weaknesses, tip, ideal } ; navigate /interview/evaluation
Retry rule: if step 2 fails, React keeps the typed answer and retries; both calls are idempotent.
```

#### Flow D — Finish and show results

```
React (Evaluation "Finish & view results" → InterviewContext.finish → api.completeInterview)
  │  POST /api/v1/interviews/{iid}/complete   (no body)
  ▼
FastAPI
  │  verify every question has an evaluation (else 409 INTERVIEW_INCOMPLETE)
  │  overall = round-half-up(mean(answer scores)); breakdown per category
  │  recommendations + two extra highlight strings (rules and/or GenAI, with rules fallback)
  │  one transaction: insert interview_results, set interviews.status=completed, update user_performance
  ▼
HTTP 200 OK  → results payload (identical to GET /interviews/{iid}/results)
  ▼
React: adapter → { meta, items:[{q, ev}], extraStrength, extraImprovement, recommendations }
       history gets the new meta prepended; navigate /results
```

#### Flow E — History, results, performance

```
App start (AppContext)
  ├─ GET /api/v1/interviews?status=completed&limit=100   → history rows (dashboard, history, trend)
  └─ GET /api/v1/performance/skills                       → ordered skills
Row click (History / Dashboard)
  └─ GET /api/v1/interviews/{id}/results                  → results payload → /results
```

---

## 4. API Architecture

### 4.1 Style and conventions **[Recommended]**

| Topic | Convention |
| --- | --- |
| Style | REST over HTTPS, JSON (`application/json; charset=utf-8`); CV upload uses `multipart/form-data` |
| Base path | `/api/v1` (versioned so the contract can evolve) |
| Naming | `snake_case` fields; plural resource nouns; lowercase enum values |
| Identifiers | UUID strings, generated server-side; never sequential |
| Timestamps | ISO-8601 UTC with `Z` (e.g. `2026-09-24T14:32:10Z`) |
| Scores | integers 0–100, higher is better |
| Rounding | **round half up** everywhere averages are taken, to match the frontend's `Math.round` (Python's default `round()` is banker's rounding and would produce different values) |
| Success bodies | the resource itself — no `{success:true}` wrapper (the HTTP status already conveys success) |
| Error bodies | uniform `error` envelope (Section 18) |
| Authentication | `Authorization: Bearer <access_token>` on every endpoint except register, login, refresh and health (**[Open]** OD-1) |
| Idempotency | achieved naturally: `PUT answer` is an upsert, `POST evaluation` / `POST complete` return the stored result if repeated |
| Pagination | `limit` (default 50, max 100) and `offset` on list endpoints |
| Unknown / foreign resources | return `404` (not `403`) so IDs cannot be probed |
| Docs | FastAPI's generated OpenAPI document should be kept in sync with this specification |

**Why no `success` wrapper.** The example envelope in the brief is reasonable but redundant here: the frontend already branches on HTTP status and only needs a stable error code and message. Keeping success bodies unwrapped matches FastAPI's natural output and lets adapter code stay small.

### 4.2 Logical layers (design only)

```
                        ┌────────────────────────────────────────────┐
React (Vite SPA)  ───►  │ API layer     routers, auth dependency,     │
 api.js adapter         │               validation (request/response) │
                        ├────────────────────────────────────────────┤
                        │ Service layer deterministic business rules  │
                        │   interview lifecycle · aggregation ·       │
                        │   scoring contract · authorization          │
                        ├───────────────┬──────────────┬─────────────┤
                        │ ML adapter    │ GenAI adapter│ File/CV      │
                        │ embeddings,   │ provider-    │ parsing,     │
                        │ scorer        │ agnostic     │ S3 storage   │
                        ├───────────────┴──────────────┴─────────────┤
                        │ Repository layer  (RDS: PostgreSQL | MySQL) │
                        └────────────────────────────────────────────┘
```

The ML and GenAI adapters sit behind interfaces so that the provider decision (OD-3), the question source (OD-5) and the scoring method (OD-8) can change without changing endpoints.

### 4.3 Request lifecycle

1. API Gateway receives the request and forwards it to the FastAPI service on EC2 (Section 20).
2. FastAPI assigns a `request_id`, authenticates, validates, and checks ownership of every referenced resource.
3. The service layer runs deterministic logic; ML / GenAI adapters are called only where Section 16 says so.
4. Database writes for one operation happen in one transaction.
5. The response (or the error envelope) is returned with `X-Request-ID`; structured logs go to CloudWatch.

### 4.4 Endpoint catalog

**Priority classes**

- **Core** — maps directly to one of the nine existing `api.js` functions. Required for the current UI to work.
- **Supporting** — required for a multi-user MVP, but the current UI has no function for it; needs a small frontend change.
- **Recommended** — improves robustness (refresh recovery, cleanup, aggregation); not required for the first demo.

| ID | Method | Path | Group | Purpose | Class |
| --- | --- | --- | --- | --- | --- |
| E01 | POST | `/auth/register` | Auth | Create account | Supporting (OD-1) |
| E02 | POST | `/auth/login` | Auth | Obtain tokens | Supporting (OD-1) |
| E03 | POST | `/auth/refresh` | Auth | Renew access token | Supporting (OD-1) |
| E04 | POST | `/auth/logout` | Auth | Revoke refresh token | Supporting (OD-1) |
| E05 | GET | `/users/me` | Profile | Current user | Supporting |
| E06 | PATCH | `/users/me` | Profile | Update name / email — `updateProfile()` | **Core** |
| E07 | POST | `/cvs` | CV | Upload + parse CV — `uploadCV()` | **Core** |
| E08 | GET | `/cvs` | CV | List own CVs (newest first) | Recommended |
| E09 | GET | `/cvs/{cv_id}` | CV | One CV with extracted data | Recommended |
| E10 | DELETE | `/cvs/{cv_id}` | CV | Delete CV and file | Supporting |
| E11 | POST | `/interviews` | Interview | Create interview + questions — `startInterview()` | **Core** |
| E12 | GET | `/interviews/{interview_id}` | Interview | Session state (resume) | Recommended |
| E13 | POST | `/interviews/{interview_id}/abandon` | Interview | Mark abandoned (Exit) | Recommended |
| E14 | POST | `/interviews/{interview_id}/complete` | Interview | Aggregate + results — `completeInterview()` | **Core** |
| E15 | PUT | `/interviews/{interview_id}/questions/{question_id}/answer` | Answer | Store answer — `submitAnswer()` | **Core** |
| E16 | POST | `/interviews/{interview_id}/questions/{question_id}/evaluation` | Evaluation | Evaluate answer — `getEvaluation()` | **Core** |
| E17 | GET | `/interviews/{interview_id}/questions/{question_id}/evaluation` | Evaluation | Fetch stored evaluation | Recommended |
| E18 | GET | `/interviews/{interview_id}/results` | Results | Results payload — `getInterviewResults()` | **Core** |
| E19 | GET | `/interviews` | History | Completed interviews — `getInterviewHistory()` | **Core** |
| E20 | GET | `/performance/skills` | Performance | Skill scores — `getSkills()` | **Core** |
| E21 | GET | `/performance/summary` | Performance | Dashboard stats + trend | Recommended |
| E22 | GET | `/health` | Operations | Liveness/readiness | Supporting |

**Totals: 22 endpoints = 9 Core + 7 Supporting + 6 Recommended.** All paths are relative to `/api/v1`. The Questions group (Section 8) has no standalone endpoint: questions are created by E11 and read through E11/E12.

### 4.5 Operational endpoint

### E22 — `GET /api/v1/health`

- **Purpose:** liveness/readiness probe for API Gateway, CloudWatch checks and deployment scripts. Not used by the frontend.
- **Auth:** none. Exposes no secrets, versions of dependencies, hostnames or user data.
- **Response `200 OK`** when the service can serve traffic:

| Field | Type | Notes |
| --- | --- | --- |
| `status` | `"ok"` | |
| `version` | string | application version |
| `checks.database` | `"ok"` | `SELECT 1` succeeded |
| `checks.models` | `"ok"` | embedding/scoring models loaded (Section 16.6) |
| `checks.storage` | `"ok"` | S3 bucket reachable |
| `checks.genai` | `"ok"` \| `"disabled"` \| `"degraded"` | informational only: GenAI is optional, so it never makes the service unready |

```json
{ "status": "ok", "version": "0.1.0",
  "checks": { "database": "ok", "models": "ok", "storage": "ok", "genai": "disabled" } }
```

- **Not ready: `503 Service Unavailable`** with the same shape, `"status": "unavailable"` and the failing check set to `"unavailable"`. This probe is the one deliberate exception to the error envelope, because monitors read the body directly.
- **Database:** a trivial connectivity query. **AI/ML:** reports whether models are loaded; runs no inference.

---

## 5. Authentication

### 5.1 Status

**[Open] OD-1.** The proposal does not mention authentication, and the frontend has no login, registration or token handling (F10). A method must be chosen before the user-scoped endpoints can be finalised. This section specifies a **[Recommended]** baseline so the rest of the API can be designed consistently; if OD-1 resolves differently, only E01–E04 and the token mechanics change — every other endpoint only assumes "an authenticated user is available".

| Option | Effect on this specification |
| --- | --- |
| **A. Email + password, JWT access token + refresh token** (baseline used below) | E01–E04 as written; `users.password_hash`, `refresh_tokens` table |
| B. Managed identity provider (for example Amazon Cognito) | E01–E04 replaced by the provider's flows; backend only validates tokens. Cognito is an AWS service **not named in the proposal** |
| C. No login for the capstone demo (single seeded user) | E01–E04 dropped; all data scoped to one demo user; **not suitable for real users' CVs** |

### 5.2 Baseline token model (Option A)

| Item | Value |
| --- | --- |
| Access token | signed JWT, short-lived (**[Recommended]** 15 minutes), sent as `Authorization: Bearer …`, kept in memory by the SPA |
| Refresh token | opaque random value, rotated on each use, stored **hashed** server-side; delivery by `HttpOnly; Secure` cookie scoped to `/api/v1/auth` (**[Open]** cookie vs response body — cookie avoids exposing it to scripts but needs CORS credentials and a CSRF review) |
| Password storage | salted slow hash (argon2id or bcrypt); never logged or returned |
| Password policy | **[Recommended]** minimum 8 characters |
| Expiry handling | access-token expiry returns `401 TOKEN_EXPIRED`; the frontend refreshes once and retries (FC-4, FC-6) |

### E01 — `POST /api/v1/auth/register`

- **Purpose:** create an account.
- **Auth:** none.
- **Request body (JSON)**

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `name` | string | yes | trimmed, 2–100 chars (matches the Profile form minimum of 2) |
| `email` | string | yes | valid email, lower-cased, unique |
| `password` | string | yes | ≥ 8 chars |

```json
{ "name": "Alex Morgan", "email": "alex.morgan@email.com", "password": "correct-horse-battery" }
```

- **Response `201 Created`**

| Field | Type | Notes |
| --- | --- | --- |
| `user` | User | see Section 17 |
| `access_token` | string | JWT |
| `token_type` | string | `"bearer"` |
| `expires_in` | integer | seconds |

```json
{
  "user": { "id": "3f2b8c1e-7d4a-4e59-9c0b-2a1f6e8d4b10", "name": "Alex Morgan",
            "email": "alex.morgan@email.com", "created_at": "2026-10-08T09:12:44Z" },
  "access_token": "<jwt>", "token_type": "bearer", "expires_in": 900
}
```

- **Status codes:** 201 · 409 · 422 · 429 · 503
- **Errors:** `EMAIL_ALREADY_REGISTERED` (409), `VALIDATION_ERROR` (422), `RATE_LIMITED` (429), `DATABASE_UNAVAILABLE` (503)
- **Database:** insert `users`; insert `refresh_tokens` (hashed).
- **AI/ML:** none.

### E02 — `POST /api/v1/auth/login`

- **Purpose:** exchange credentials for tokens. **Auth:** none.
- **Request:** `{ "email": string (required), "password": string (required) }`
- **Response `200 OK`:** same shape as E01.
- **Status codes:** 200 · 401 · 422 · 429 · 503
- **Errors:** `INVALID_CREDENTIALS` (401 — identical message for unknown email and wrong password), `RATE_LIMITED` (429)
- **Database:** read `users`; insert `refresh_tokens`.

### E03 — `POST /api/v1/auth/refresh`

- **Purpose:** issue a new access token and rotate the refresh token. **Auth:** refresh token (cookie, or body field `refresh_token` if OD-1 chooses body delivery).
- **Response `200 OK`:** `{ "access_token": string, "token_type": "bearer", "expires_in": integer }`
- **Status codes:** 200 · 401 · 503
- **Errors:** `TOKEN_INVALID`, `TOKEN_EXPIRED` (both 401)
- **Database:** read + rotate `refresh_tokens`.

### E04 — `POST /api/v1/auth/logout`

- **Purpose:** revoke the current refresh token. **Auth:** Bearer.
- **Response `204 No Content`.** Always succeeds if the token is already revoked.
- **Database:** mark `refresh_tokens.revoked_at`.

---

## 6. CV API

CVs contain personal data (Section 19). All endpoints are scoped to the authenticated user; a CV that belongs to someone else is reported as `CV_NOT_FOUND`.

### E07 — `POST /api/v1/cvs`  (frontend: `uploadCV`)

- **Purpose:** upload a CV, validate it, store the file, extract text and structured information.
- **Auth:** Bearer required.
- **Content-Type:** `multipart/form-data`

| Part | Type | Required | Rules |
| --- | --- | --- | --- |
| `file` | binary | yes | extension `pdf` or `docx`; **≤ 5 MB (5 × 1024 × 1024 bytes — the frontend rejects anything larger)**; content must match the extension (magic bytes); not encrypted/password-protected; must yield extractable text |

No other parts are accepted.

- **Example request**

```
POST /api/v1/cvs HTTP/1.1
Authorization: Bearer <token>
Content-Type: multipart/form-data; boundary=----aic

------aic
Content-Disposition: form-data; name="file"; filename="cv.pdf"
Content-Type: application/pdf

<binary>
------aic--
```

- **Response `201 Created`**

| Field | Type | Notes |
| --- | --- | --- |
| `cv.id` | uuid | the only value the UI currently stores for later use |
| `cv.original_filename` | string | sanitised name as received |
| `cv.extension` | `"pdf"` \| `"docx"` | |
| `cv.size_bytes` | integer | |
| `cv.parse_status` | `"parsed"` | always `parsed` in MVP (failed parses are rejected, not stored); reserved for asynchronous parsing later |
| `cv.created_at` | timestamp | |
| `extracted.skills` | string[] | used to personalise questions; may be empty |
| `extracted.experience` / `.education` / `.projects` | string[] | **provisional** free-text lines; shape depends on OD-4; may be empty |

```json
{
  "cv": {
    "id": "9d4e6a52-1b7c-4f3e-8a21-5c0d7b9e3f64",
    "original_filename": "cv.pdf",
    "extension": "pdf",
    "size_bytes": 124318,
    "parse_status": "parsed",
    "created_at": "2026-10-08T09:20:03Z"
  },
  "extracted": {
    "skills": ["Python", "PyTorch", "FastAPI", "SQL", "Transformers"],
    "experience": ["ML Engineer Intern — Acme Analytics (2025)"],
    "education": ["B.Sc. Computer Science"],
    "projects": ["Ticket-routing text classifier"]
  }
}
```

- **Status codes:** 201 · 401 · 413 · 415 · 422 · 429 · 503
- **Errors:** `UNSUPPORTED_FILE_TYPE` (415), `FILE_TOO_LARGE` (413), `CV_UNREADABLE` (422 — corrupt, encrypted, image-only/scanned with no text, or below the minimum text length), `VALIDATION_ERROR` (422 — missing/extra parts), `STORAGE_UNAVAILABLE` / `DATABASE_UNAVAILABLE` (503), `RATE_LIMITED` (429)
- **Database:** insert `cvs` (+ S3 object key), `cv_profiles`, `cv_skills` in one transaction; if the transaction fails the S3 object is removed.
- **AI/ML:** text extraction (deterministic); structured extraction (method **[Open]** OD-4). No external GenAI call is required for upload.
- **Notes:** the UI shows "Uploading & analyzing…" while this request runs, so parsing is **synchronous**. Progress percentages come from the browser's upload events, not from the server (F14). A user may hold several CVs; the UI uses the newest.

### E08 — `GET /api/v1/cvs`

- **Purpose:** list the user's CVs, newest first — lets the UI restore the CV after a refresh (F9). **Auth:** Bearer.
- **Query:** `limit` (int, default 50, max 100), `offset` (int, default 0).
- **Response `200 OK`:** `{ "items": [ CV ], "total": integer, "limit": integer, "offset": integer }` where `CV` is the `cv` object from E07.
- **Status codes:** 200 · 401 · 503. **Database:** read `cvs` where `deleted_at IS NULL`.

### E09 — `GET /api/v1/cvs/{cv_id}`

- **Purpose:** one CV with its extracted data. **Auth:** Bearer.
- **Response `200 OK`:** same body as the E07 response.
- **Errors:** `CV_NOT_FOUND` (404). **Database:** read `cvs`, `cv_profiles`, `cv_skills`.

### E10 — `DELETE /api/v1/cvs/{cv_id}`

- **Purpose:** remove a CV and its stored data (backs the UI's "Remove" button, which today only clears local state). **Auth:** Bearer.
- **Response `204 No Content`.**
- **Effects:** deletes the S3 object, `extracted_text`, `cv_profiles`, `cv_skills`. Interviews that used this CV are **kept**; their `cv_id` becomes `NULL` so history and results remain valid.
- **Errors:** `CV_NOT_FOUND` (404; also returned on a repeated delete). **Database:** delete/anonymise as above in one transaction.

---

## 7. Interview API

An *interview* is one practice session: a CV, a target role, a type, a difficulty, and *n* questions generated up front. Lifecycle: `in_progress → completed` or `in_progress → abandoned`.

### E11 — `POST /api/v1/interviews`  (frontend: `startInterview`)

- **Purpose:** create an interview and generate all of its questions in one call (the UI needs `questions` immediately to render "Question 1 of n" and the progress bar).
- **Auth:** Bearer required.
- **Request body (JSON)**

| Field | Type | Required | Rules / frontend source |
| --- | --- | --- | --- |
| `cv_id` | uuid | **yes** | the uploaded CV; must belong to the caller. **Not sent by the UI today (F1)** |
| `target_role` | string | yes | trimmed, 3–100 chars; free text (preset chips or custom input) |
| `interview_type` | enum | yes | `technical` · `behavioral` · `mixed` |
| `difficulty` | enum | yes | `beginner` · `intermediate` · `advanced` |
| `question_count` | integer | yes | one of `5`, `10`, `15` |

```json
{
  "cv_id": "9d4e6a52-1b7c-4f3e-8a21-5c0d7b9e3f64",
  "target_role": "AI Engineer",
  "interview_type": "technical",
  "difficulty": "intermediate",
  "question_count": 5
}
```

- **Response `201 Created`**

| Field | Type | Notes |
| --- | --- | --- |
| `id` | uuid | becomes `session.id` |
| `status` | enum | `in_progress` |
| `config` | object | echo of the request (minus `cv_id`) plus `cv_id` |
| `questions[]` | array | exactly `question_count` items, ordered by `position` |
| `questions[].id` | uuid | needed for answer/evaluation calls (F2) |
| `questions[].position` | integer | 1-based |
| `questions[].text` | string | |
| `questions[].type` | enum | `technical` · `behavioral` |
| `created_at` | timestamp | |

The response **never contains ideal answers** (Section 8).

```json
{
  "id": "b8f1c0de-5a4e-4b8e-9a52-1f6d0c3e7a10",
  "status": "in_progress",
  "config": {
    "cv_id": "9d4e6a52-1b7c-4f3e-8a21-5c0d7b9e3f64",
    "target_role": "AI Engineer",
    "interview_type": "technical",
    "difficulty": "intermediate",
    "question_count": 5
  },
  "questions": [
    { "id": "0a7c5e31-2d94-4c1b-b6f8-3e9a1d5c7b02", "position": 1, "type": "technical",
      "text": "Can you explain a machine learning project you worked on and the impact it had?" },
    { "id": "6e1d9b47-8f30-4a25-9c7e-d2b4a8f10c35", "position": 2, "type": "technical",
      "text": "Your CV mentions a transformer-based classifier. How did you choose and evaluate the model?" },
    { "id": "1b8f3a72-5c09-4e64-a1d7-9e2c0f6b4d83", "position": 3, "type": "technical",
      "text": "How would you handle an imbalanced dataset in a classification task?" },
    { "id": "d94a7c15-3e82-4b06-8f5a-6c1b0e9d2a47", "position": 4, "type": "technical",
      "text": "Describe how you deployed a model or service to the cloud." },
    { "id": "4f6e2d90-7a13-4c58-b9e0-8d3a5c1f7e26", "position": 5, "type": "technical",
      "text": "What is the difference between BERT and Sentence Transformers for similarity tasks?" }
  ],
  "created_at": "2026-10-08T09:31:15Z"
}
```

- **Status codes:** 201 · 401 · 404 · 422 · 429 · 503 · 504
- **Errors:** `CV_REQUIRED` (422 — `cv_id` absent/null; the UI shows "upload your CV first"), `CV_NOT_FOUND` (404), `INVALID_INTERVIEW_CONFIG` (422, with per-field `details`), `AI_SERVICE_UNAVAILABLE` (503), `AI_SERVICE_TIMEOUT` (504), `RATE_LIMITED` (429), `DATABASE_UNAVAILABLE` (503)
- **Database:** insert `interviews`, then *n* rows in `interview_questions` (including the hidden `ideal_answer`), written **only after generation succeeds** so a failed call leaves nothing behind and the client can safely retry.
- **AI/ML:** question selection/generation and ideal-answer generation (Section 16, steps C–D). The call is synchronous because the UI shows "Generating questions…". The latency budget must stay below the API Gateway timeout (Section 20); generating all questions (and ideal answers) in batched rather than per-question model calls is **[Recommended]**.

### E12 — `GET /api/v1/interviews/{interview_id}`

- **Purpose:** current state of one interview, so the UI can recover after a refresh (F12). **Auth:** Bearer.
- **Response `200 OK`**

| Field | Type | Notes |
| --- | --- | --- |
| `id`, `status`, `config`, `created_at` | | as E11 |
| `completed_at` | timestamp \| null | |
| `progress` | `{answered, evaluated, total}` | integers |
| `current_position` | integer \| null | position of the first question without an evaluation; `null` when none left |
| `questions[]` | array | as E11, plus `state`: `pending` · `answered` · `evaluated` |

```json
{
  "id": "b8f1c0de-5a4e-4b8e-9a52-1f6d0c3e7a10",
  "status": "in_progress",
  "config": { "cv_id": "9d4e6a52-1b7c-4f3e-8a21-5c0d7b9e3f64", "target_role": "AI Engineer",
              "interview_type": "technical", "difficulty": "intermediate", "question_count": 5 },
  "created_at": "2026-10-08T09:31:15Z",
  "completed_at": null,
  "progress": { "answered": 1, "evaluated": 1, "total": 5 },
  "current_position": 2,
  "questions": [
    { "id": "0a7c5e31-2d94-4c1b-b6f8-3e9a1d5c7b02", "position": 1, "type": "technical", "state": "evaluated",
      "text": "Can you explain a machine learning project you worked on and the impact it had?" },
    { "id": "6e1d9b47-8f30-4a25-9c7e-d2b4a8f10c35", "position": 2, "type": "technical", "state": "pending",
      "text": "Your CV mentions a transformer-based classifier. How did you choose and evaluate the model?" }
  ]
}
```

(The example is truncated to two of the five questions.)

- **Errors:** `INTERVIEW_NOT_FOUND` (404). **Database:** read `interviews`, `interview_questions`, `answers`, `evaluations`.

### E13 — `POST /api/v1/interviews/{interview_id}/abandon`

- **Purpose:** mark an interview as abandoned when the user confirms "Exit". **Auth:** Bearer.
- **Request:** no body. **Response `200 OK`:** `{ "id": uuid, "status": "abandoned" }`. Repeating the call returns the same `200`.
- **Errors:** `INTERVIEW_NOT_FOUND` (404), `INTERVIEW_NOT_ACTIVE` (409 — already completed).
- **Database:** update `interviews.status`. Abandoned interviews are excluded from history, results and performance.

### E14 — `POST /api/v1/interviews/{interview_id}/complete`  (frontend: `completeInterview`)

- **Purpose:** finish the interview, aggregate all stored evaluations, persist the results and update the user's performance.
- **Auth:** Bearer. **Request:** no body. The frontend currently sends `{session, config, items}`; those values are **ignored** (F4).
- **Preconditions:** every question has an evaluation.
- **Response `200 OK`:** the full **results payload**, identical to E18 (see Section 11 for fields and example). If the interview is already completed, the stored payload is returned unchanged (idempotent).
- **Status codes:** 200 · 401 · 404 · 409 · 503
- **Errors:** `INTERVIEW_INCOMPLETE` (409; `details` lists unevaluated positions), `INTERVIEW_NOT_FOUND` (404), `INTERVIEW_NOT_ACTIVE` (409 — abandoned), `DATABASE_UNAVAILABLE` (503). A failure of the optional GenAI wording step does **not** fail the call; it falls back to rule-based text (Section 16).
- **Database (single transaction):** insert `interview_results`; set `interviews.status = completed`, `completed_at`, `overall_score`; upsert `user_performance` rows.
- **AI/ML:** deterministic aggregation; recommendation wording by rules and/or GenAI.

---

## 8. Question API

Questions have no endpoint of their own. They are **created** by E11 and **read** through E11 (on creation) and E12 (session recovery). This section defines the resource and its rules.

### 8.1 Question resource

| Field | Type | Visible to client | Notes |
| --- | --- | --- | --- |
| `id` | uuid | yes | |
| `interview_id` | uuid | implied by path | |
| `position` | integer | yes | 1-based, unique within the interview. The frontend's `index` equals `position − 1` |
| `text` | string | yes | |
| `type` | `technical` \| `behavioral` | yes | drives the "Technical Question" / "Behavioral Question" chip |
| `ideal_answer` | string | **no — only after the question has an evaluation** (returned inside the evaluation as `ideal_answer`) | stored at creation; used as the reference for scoring (Section 16, step E) |
| `source` | `bank` \| `genai` | no | provenance, for analytics |

### 8.2 Rules

1. **Count.** Exactly `question_count` questions, with distinct texts inside one interview (F15).
2. **Type mix.** `technical` → all technical; `behavioral` → all behavioral; `mixed` → a blend. The exact ratio is an implementation detail; **[Recommended]** a configurable default of roughly 60 % technical / 40 % behavioral.
3. **Difficulty and role** influence selection or the generation prompt; **CV skills** influence personalization (Section 16, step C).
4. **Ideal answers are secret until evaluated.** Revealing them before the user answers would defeat the exercise and leak the scoring reference. They never appear in E11 or E12.
5. **Immutable.** Questions are not edited after creation. Dynamic follow-up questions are a future capability (F21, Section 22).

---

## 9. Answer API

### E15 — `PUT /api/v1/interviews/{interview_id}/questions/{question_id}/answer`  (frontend: `submitAnswer`)

- **Purpose:** store (or replace) the candidate's text answer for one question. `PUT` makes retries safe: the UI keeps the typed text after a failure and may resubmit.
- **Auth:** Bearer required.
- **Request body (JSON)**

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `answer_text` | string | yes | after trimming: non-empty; **≥ 30** characters; **≤ 1500** characters (identical to the UI limits) |

```json
{ "answer_text": "At my last internship I built a ticket-routing classifier. I fine-tuned DistilBERT on 40k labelled tickets, compared it with a TF-IDF baseline and improved macro-F1 from 0.71 to 0.89, cutting triage time by about 30%." }
```

- **Response:** `201 Created` the first time, `200 OK` when an existing answer is replaced.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | uuid | |
| `interview_id`, `question_id` | uuid | |
| `answer_text` | string | trimmed |
| `char_count` | integer | |
| `input_mode` | `"text"` | `"speech"` reserved for the future (OD-6) |
| `submitted_at`, `updated_at` | timestamp | |

```json
{
  "id": "c5a92e08-4b17-4d6f-a3e1-7f0b8d2c6e94",
  "interview_id": "b8f1c0de-5a4e-4b8e-9a52-1f6d0c3e7a10",
  "question_id": "0a7c5e31-2d94-4c1b-b6f8-3e9a1d5c7b02",
  "answer_text": "At my last internship I built a ticket-routing classifier. I fine-tuned DistilBERT on 40k labelled tickets, compared it with a TF-IDF baseline and improved macro-F1 from 0.71 to 0.89, cutting triage time by about 30%.",
  "char_count": 219,
  "input_mode": "text",
  "submitted_at": "2026-10-08T09:36:02Z",
  "updated_at": "2026-10-08T09:36:02Z"
}
```

- **Status codes:** 200 · 201 · 401 · 404 · 409 · 422 · 503
- **Errors:** `ANSWER_EMPTY` (422), `ANSWER_TOO_SHORT` (422), `ANSWER_TOO_LONG` (422), `INTERVIEW_NOT_FOUND` / `QUESTION_NOT_FOUND` (404), `INTERVIEW_NOT_ACTIVE` (409 — completed or abandoned), `ANSWER_ALREADY_EVALUATED` (409 — answers are locked once evaluated; the UI never re-answers), `DATABASE_UNAVAILABLE` (503)
- **Database:** upsert `answers` (unique on `question_id`).
- **AI/ML:** none. The answer is untrusted text (it will later be embedded and possibly placed in an LLM prompt — Section 19).
- **Notes:** answers may be submitted in any order; the server does not enforce sequence, only that `complete` (E14) requires all questions evaluated. Length is counted in Unicode code points; JavaScript's `.length` counts UTF-16 units, so text with emoji can pass the UI's 30-character check yet be shorter server-side — the server is authoritative.

---

## 10. Evaluation API

### E16 — `POST /api/v1/interviews/{interview_id}/questions/{question_id}/evaluation`  (frontend: `getEvaluation`)

- **Purpose:** score the stored answer against the stored ideal answer and generate feedback. The UI shows a "thinking" indicator while this runs.
- **Auth:** Bearer required. **Request:** no body (the answer was stored by E15; the frontend's extra `question`/`answer` arguments are not needed).
- **Idempotency:** if an evaluation already exists it is returned with `200`; otherwise it is created with `201`. Concurrent duplicate requests resolve to a single stored row.
- **Response fields**

| Field | Type | Notes |
| --- | --- | --- |
| `id` | uuid | |
| `question_id` | uuid | |
| `overall_score` | integer 0–100 | `ev.score` in the UI; the answer's headline score |
| `category_scores.relevance` | integer 0–100 | UI label "Relevance" |
| `category_scores.clarity` | integer 0–100 | "Clarity" |
| `category_scores.technical_depth` | integer 0–100 | "Technical Depth" |
| `category_scores.confidence` | integer 0–100 | "Confidence" |
| `strengths` | string[] | **1–3** items (the UI renders every item; an empty array would show an empty card) |
| `weaknesses` | string[] | **1–3** items |
| `improvement_tip` | string | one suggestion (`ev.tip`) |
| `ideal_answer` | string | example of a stronger answer, revealed only now (`ev.ideal`); the UI labels it "Example — not your answer" |
| `feedback_source` | `"rules"` \| `"genai"` | how the wording was produced (UI ignores it) |
| `scoring_version` | string | identifies the scoring configuration used, for reproducibility |
| `created_at` | timestamp | |

```json
{
  "id": "e2d7f4a9-6c18-4b05-8d93-0a5b1c7e3f26",
  "question_id": "0a7c5e31-2d94-4c1b-b6f8-3e9a1d5c7b02",
  "overall_score": 82,
  "category_scores": { "relevance": 86, "clarity": 79, "technical_depth": 77, "confidence": 81 },
  "strengths": [
    "Clearly explained the technical approach.",
    "Demonstrated practical experience.",
    "Provided relevant examples."
  ],
  "weaknesses": [
    "The answer was brief; add more depth and detail.",
    "Could quantify the project impact more clearly.",
    "The answer could be more structured."
  ],
  "improvement_tip": "Use the STAR method (Situation, Task, Action, Result) and close with a measurable outcome.",
  "ideal_answer": "At my last internship I built a ticket-routing classifier. The problem was 30% manual triage delay, so I fine-tuned DistilBERT on 40k labelled tickets, compared it against a TF-IDF baseline, and tracked macro-F1. Accuracy rose from 71% to 89%, cutting triage time by about 30%. I deployed it behind a FastAPI service and monitored drift weekly.",
  "feedback_source": "rules",
  "scoring_version": "v0-draft",
  "created_at": "2026-10-08T09:36:06Z"
}
```

- **Status codes:** 200 · 201 · 401 · 404 · 409 · 503 · 504
- **Errors:** `ANSWER_NOT_FOUND` (404 — no answer stored yet), `QUESTION_NOT_FOUND` / `INTERVIEW_NOT_FOUND` (404), `INTERVIEW_NOT_ACTIVE` (409), `AI_SERVICE_UNAVAILABLE` (503, `retryable: true`), `AI_SERVICE_TIMEOUT` (504, `retryable: true`), `DATABASE_UNAVAILABLE` (503)
- **Database:** read `answers`, `interview_questions` (ideal answer); insert `evaluations` with diagnostics (raw similarity, model versions, latency).
- **AI/ML:** semantic similarity and category scoring (ML), feedback wording (rules and/or GenAI) — Section 16, steps E–H.
- **Degradation policy:** if the **ML scoring** step fails the call fails (`AI_SERVICE_UNAVAILABLE`) because a score cannot be fabricated. If only the optional **GenAI wording** step fails or times out, the server falls back to rule-based strengths/weaknesses/tip and sets `feedback_source: "rules"`.
- **Latency:** a target and hard cap must be set by the ML/GenAI owners (**[Open]** OD-13). Any synchronous call must finish within the API Gateway limit (Section 20).

### E17 — `GET /api/v1/interviews/{interview_id}/questions/{question_id}/evaluation`

- **Purpose:** fetch a stored evaluation (recovery after refresh or a lost response). **Auth:** Bearer.
- **Response `200 OK`:** same body as E16. **Errors:** `EVALUATION_NOT_FOUND` (404), `QUESTION_NOT_FOUND` (404), `INTERVIEW_NOT_FOUND` (404).
- **Database:** read `evaluations`.

---

## 11. Results API

### E18 — `GET /api/v1/interviews/{interview_id}/results`  (frontend: `getInterviewResults`)

E14 returns exactly this payload when an interview is completed.

- **Purpose:** the complete results for one completed interview.
- **Auth:** Bearer required.
- **Response fields**

| Field | Type | UI use |
| --- | --- | --- |
| `interview` | InterviewSummary | header card (`meta`): `id, completed_at, target_role, interview_type, difficulty, question_count, overall_score, status` |
| `breakdown.confidence` / `.relevance` / `.clarity` / `.technical_depth` / `.communication` | integer 0–100 | "Performance breakdown" bars; `technical_depth` is shown as *Technical Knowledge* here (F8) |
| `additional_strength` | string | third item under "Strengths" (`extraStrength`) |
| `additional_improvement` | string | third item under "Areas for improvement" (`extraImprovement`) |
| `recommendations` | string[3] | "AI recommendations" |
| `generated_by` | `"rules"` \| `"genai"` | provenance of the three strings above |
| `items[]` | array | question-by-question list, ordered by `position` |
| `items[].position` | integer | |
| `items[].question` | `{id, text, type}` | `q` |
| `items[].answer_text` | string | not displayed today (F17) |
| `items[].evaluation` | Evaluation | same object as E16 (`ev`) |

**Calculation rules (so server and client always agree)**

| Value | Rule |
| --- | --- |
| `interview.overall_score` | round-half-up of the mean of the answers' `overall_score` |
| `breakdown.<category>` | round-half-up of the mean of that category over all answers |
| `breakdown.communication` | round-half-up of `(breakdown.clarity + breakdown.confidence) / 2`, using the **already rounded** values (as the frontend does) |
| Strengths / improvements list | chosen client-side from the top 2 / bottom 2 breakdown values, plus the two `additional_*` strings (see Section 2.6) |
| Label (Excellent / Strong / Needs Improvement) | client-side thresholds 88 / 78 — scoring must be calibrated so the distribution suits them (OD-8) |

```json
{
  "interview": {
    "id": "a3c9e5f1-6b27-4d80-9e14-7f0a2b8c5d63",
    "completed_at": "2026-09-24T14:32:10Z",
    "target_role": "AI Engineer",
    "interview_type": "technical",
    "difficulty": "intermediate",
    "question_count": 10,
    "overall_score": 84,
    "status": "completed"
  },
  "breakdown": { "confidence": 83, "relevance": 88, "clarity": 81, "technical_depth": 79, "communication": 82 },
  "additional_strength": "Relevant, practical examples",
  "additional_improvement": "Quantifying impact",
  "recommendations": [
    "Explain technical projects in under 2 minutes.",
    "Give measurable results for past projects.",
    "Structure behavioral answers using STAR."
  ],
  "generated_by": "rules",
  "items": [
    {
      "position": 1,
      "question": { "id": "0a7c5e31-2d94-4c1b-b6f8-3e9a1d5c7b02", "type": "technical",
                    "text": "Can you explain a machine learning project you worked on and the impact it had?" },
      "answer_text": "At my last internship I built a ticket-routing classifier…",
      "evaluation": {
        "id": "e2d7f4a9-6c18-4b05-8d93-0a5b1c7e3f26",
        "question_id": "0a7c5e31-2d94-4c1b-b6f8-3e9a1d5c7b02",
        "overall_score": 88,
        "category_scores": { "relevance": 92, "clarity": 85, "technical_depth": 83, "confidence": 87 },
        "strengths": ["Clearly explained the technical approach."],
        "weaknesses": ["Could quantify the project impact more clearly."],
        "improvement_tip": "Use the STAR method (Situation, Task, Action, Result) and close with a measurable outcome.",
        "ideal_answer": "At my last internship I built a ticket-routing classifier…",
        "feedback_source": "rules",
        "scoring_version": "v0-draft",
        "created_at": "2026-09-24T14:05:41Z"
      }
    }
  ]
}
```

(`items` is shortened to one of ten entries for readability; the real payload always contains `question_count` items.)

- **Status codes:** 200 · 401 · 404 · 409 · 503
- **Errors:** `INTERVIEW_NOT_FOUND` (404), `RESULTS_NOT_AVAILABLE` (409 — interview not completed)
- **Database:** read `interview_results`, `interviews`, `interview_questions`, `answers`, `evaluations`.
- **AI/ML:** none at read time — everything was computed and stored by E14.

---

## 12. History API

### E19 — `GET /api/v1/interviews`  (frontend: `getInterviewHistory`)

- **Purpose:** the user's completed interviews, newest first.
- **Auth:** Bearer required.
- **Query parameters**

| Param | Type | Default | Notes |
| --- | --- | --- | --- |
| `status` | enum | `completed` | only `completed` is supported in MVP (F24); other values → `VALIDATION_ERROR` |
| `type` | enum | — | optional `technical` · `behavioral` · `mixed`. The UI filters client-side today, so this is optional |
| `limit` | integer | 50 | 1–100 |
| `offset` | integer | 0 | |

Sort order is fixed: `completed_at` descending (the Dashboard's `history.slice(0, 3)` assumes newest first).

- **Response `200 OK`:** `{ "items": [HistoryItem], "total": integer, "limit": integer, "offset": integer }`

| HistoryItem field | Type | Frontend field |
| --- | --- | --- |
| `id` | uuid | `id` |
| `completed_at` | timestamp | `date` (formatted by the adapter, e.g. `Sep 24, 2026`) |
| `target_role` | string | `role` |
| `interview_type` | enum | `type` |
| `difficulty` | enum | `diff` |
| `question_count` | integer | `n` |
| `overall_score` | integer | `score` |
| `status` | `"completed"` | `status` (`"Completed"`) |

```json
{
  "items": [
    { "id": "a3c9e5f1-6b27-4d80-9e14-7f0a2b8c5d63", "completed_at": "2026-09-24T14:32:10Z", "target_role": "AI Engineer",
      "interview_type": "technical", "difficulty": "intermediate", "question_count": 10, "overall_score": 84, "status": "completed" },
    { "id": "5d0b8e27-9c41-4a63-b7f2-1e6a3c9d0845", "completed_at": "2026-09-17T10:05:51Z", "target_role": "Machine Learning Engineer",
      "interview_type": "mixed", "difficulty": "intermediate", "question_count": 10, "overall_score": 82, "status": "completed" },
    { "id": "f1a6c3d8-2e95-4b70-8c14-a9d7e0b5362f", "completed_at": "2026-09-09T16:48:27Z", "target_role": "Data Scientist",
      "interview_type": "behavioral", "difficulty": "beginner", "question_count": 5, "overall_score": 80, "status": "completed" },
    { "id": "8e3c7a50-d1f6-4924-a0b8-6c2e9f4d7a13", "completed_at": "2026-08-30T08:21:09Z", "target_role": "AI Engineer",
      "interview_type": "technical", "difficulty": "intermediate", "question_count": 15, "overall_score": 83, "status": "completed" }
  ],
  "total": 4,
  "limit": 50,
  "offset": 0
}
```

- **Status codes:** 200 · 401 · 422 · 503. **Errors:** `VALIDATION_ERROR` (422), `UNAUTHORIZED` (401).
- **Database:** read `interviews` (index on `user_id, status, completed_at DESC`).
- **Pagination caveat (F6):** the frontend loads this list once and derives dashboard stats and the trend from it. With the cap of 100 per request, those figures are only correct for users with ≤ 100 completed interviews. Prefer E21 for aggregates.

---

## 13. Performance API

### E20 — `GET /api/v1/performance/skills`  (frontend: `getSkills`)

- **Purpose:** the user's skill scores across all completed interviews.
- **Auth:** Bearer required.
- **Definition:** each skill is the round-half-up mean, over the user's completed interviews, of that interview's `breakdown` value (every interview weighs equally). Skills: `communication`, `relevance`, `confidence`, `clarity`, `technical_depth`.
- **Ordering:** by `score` descending; ties broken in the fixed order listed above (the Dashboard shows the first four, F7).
- **Response `200 OK`**

| Field | Type | Notes |
| --- | --- | --- |
| `skills[]` | array | `{ key, label, score }` |
| `skills[].label` | string | `Communication`, `Relevance`, `Confidence`, `Clarity`, `Technical Depth` |
| `interviews_counted` | integer | |

```json
{
  "skills": [
    { "key": "communication", "label": "Communication", "score": 88 },
    { "key": "relevance", "label": "Relevance", "score": 86 },
    { "key": "confidence", "label": "Confidence", "score": 82 },
    { "key": "clarity", "label": "Clarity", "score": 81 },
    { "key": "technical_depth", "label": "Technical Depth", "score": 76 }
  ],
  "interviews_counted": 4
}
```

- **Empty state:** a user with no completed interviews gets `{ "skills": [], "interviews_counted": 0 }`. **The current frontend cannot handle this** (F26).
- **Status codes:** 200 · 401 · 503. **Database:** read `user_performance`. **AI/ML:** none.

### E21 — `GET /api/v1/performance/summary`

- **Purpose:** the figures the Dashboard and Performance page currently compute client-side (F6), without loading the whole history. **Auth:** Bearer.
- **Query:** `trend_limit` (integer, default 12, max 50).
- **Response `200 OK`**

| Field | Type | Notes |
| --- | --- | --- |
| `interviews_completed` | integer | "Interviews completed" |
| `average_score` | integer \| null | round-half-up mean of overall scores; this is the Dashboard's "Average confidence" (F16); `null` if none |
| `strongest_skill` / `weakest_skill` | `{key,label,score}` \| null | "Strongest area" / "Needs improvement" |
| `trend[]` | array | `{ interview_id, completed_at, overall_score }`, **oldest → newest**, last `trend_limit` interviews |

```json
{
  "interviews_completed": 4,
  "average_score": 82,
  "strongest_skill": { "key": "communication", "label": "Communication", "score": 88 },
  "weakest_skill": { "key": "technical_depth", "label": "Technical Depth", "score": 76 },
  "trend": [
    { "interview_id": "8e3c7a50-d1f6-4924-a0b8-6c2e9f4d7a13", "completed_at": "2026-08-30T08:21:09Z", "overall_score": 83 },
    { "interview_id": "f1a6c3d8-2e95-4b70-8c14-a9d7e0b5362f", "completed_at": "2026-09-09T16:48:27Z", "overall_score": 80 },
    { "interview_id": "5d0b8e27-9c41-4a63-b7f2-1e6a3c9d0845", "completed_at": "2026-09-17T10:05:51Z", "overall_score": 82 },
    { "interview_id": "a3c9e5f1-6b27-4d80-9e14-7f0a2b8c5d63", "completed_at": "2026-09-24T14:32:10Z", "overall_score": 84 }
  ]
}
```

- **Status codes:** 200 · 401 · 422 · 503. **Database:** read `interviews`, `user_performance`.

---

## 14. Profile API

### E05 — `GET /api/v1/users/me`

- **Purpose:** the signed-in user (replaces the hard-coded `DEMO_USER`; drives the welcome message, avatar initials and the "Sign in as {name}" button). **Auth:** Bearer.
- **Response `200 OK`:** `{ "id": uuid, "name": string, "email": string, "created_at": timestamp }`

```json
{ "id": "3f2b8c1e-7d4a-4e59-9c0b-2a1f6e8d4b10", "name": "Alex Morgan",
  "email": "alex.morgan@email.com", "created_at": "2026-10-08T09:12:44Z" }
```

- **Errors:** `UNAUTHORIZED` (401), `TOKEN_EXPIRED` (401). **Database:** read `users`.

### E06 — `PATCH /api/v1/users/me`  (frontend: `updateProfile`)

- **Purpose:** save the Profile form. **Auth:** Bearer.
- **Request body (JSON)** — at least one field:

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `name` | string | no | trimmed, 2–100 chars (UI minimum 2) |
| `email` | string | no | valid email, unique. Whether a change requires re-verification is **[Open]** (OD-1, OD-9) |

```json
{ "name": "Alex Morgan", "email": "alex.m@email.com" }
```

- **Response `200 OK`:** the updated user (same shape as E05). The UI replaces its `user` state with it.
- **Status codes:** 200 · 401 · 409 · 422 · 503
- **Errors:** `VALIDATION_ERROR` (422), `EMAIL_ALREADY_IN_USE` (409), `UNAUTHORIZED` (401)
- **Database:** update `users.name`, `users.email`, `updated_at`.
- **Not covered:** "Reset demo data" has no endpoint (OD-9). Account and data deletion is listed as a future endpoint (Section 22).

---

## 15. Database Models

The database engine is **[Open]** (OD-2: PostgreSQL or MySQL on AWS RDS, per the proposal). Types below are written generically; the mapping is:

| Generic | PostgreSQL | MySQL |
| --- | --- | --- |
| `UUID` | `uuid` | `CHAR(36)` or `BINARY(16)` |
| `TIMESTAMPTZ` | `timestamptz` | `DATETIME(6)` stored as UTC |
| `JSONB` | `jsonb` | `JSON` |
| `SMALLINT` / `INTEGER` / `BOOLEAN` / `TEXT` / `VARCHAR(n)` | same | same (`BOOLEAN` = `TINYINT(1)`) |

Nothing here has been created; this is a design for the Database Engineer (Ahmed Hamdy Ahmed) to review.

### 15.1 Entity relationships

```
User (users)
  │
  ├── RefreshToken (refresh_tokens)          1 : N   [only if OD-1 = option A]
  │
  ├── UserPerformance (user_performance)     1 : N   one row per skill (5 skills)
  │
  ├── CV (cvs)                               1 : N
  │     ├── CVProfile (cv_profiles)          1 : 1   structured extraction
  │     └── CVSkill (cv_skills)              1 : N
  │
  └── Interview (interviews)                 1 : N   (cv_id → cvs, nullable, SET NULL on CV delete)
        │
        ├── InterviewQuestion                1 : N   ordered by position, unique per interview
        │     │   (interview_questions)
        │     └── Answer (answers)           1 : 0..1
        │           └── Evaluation           1 : 0..1
        │                 (evaluations)
        └── InterviewResult                  1 : 0..1   created when the interview is completed
              (interview_results)

QuestionBank (question_bank)  ── reference data, not owned by a user; optionally referenced by
                                 interview_questions.bank_question_id   [depends on OD-5]
```

### 15.2 Tables

Legend: **PK** primary key · **FK** foreign key · *Req* = NOT NULL.

#### `users`

| Field | Type | Req | Key | Notes |
| --- | --- | --- | --- | --- |
| `id` | UUID | yes | PK | |
| `name` | VARCHAR(100) | yes | | |
| `email` | VARCHAR(254) | yes | unique | stored lower-case |
| `password_hash` | VARCHAR(255) | no | | `NULL` unless OD-1 = option A |
| `is_active` | BOOLEAN | yes | | default `true` |
| `created_at` / `updated_at` | TIMESTAMPTZ | yes | | |

#### `refresh_tokens`  *(conditional on OD-1 = option A)*

| Field | Type | Req | Key | Notes |
| --- | --- | --- | --- | --- |
| `id` | UUID | yes | PK | |
| `user_id` | UUID | yes | FK → `users.id` ON DELETE CASCADE | |
| `token_hash` | CHAR(64) | yes | unique | hash only; the raw token is never stored |
| `expires_at` | TIMESTAMPTZ | yes | | |
| `revoked_at` | TIMESTAMPTZ | no | | |
| `created_at` | TIMESTAMPTZ | yes | | |

#### `cvs`

| Field | Type | Req | Key | Notes |
| --- | --- | --- | --- | --- |
| `id` | UUID | yes | PK | |
| `user_id` | UUID | yes | FK → `users.id` ON DELETE CASCADE | |
| `original_filename` | VARCHAR(255) | yes | | sanitised |
| `extension` | VARCHAR(4) | yes | | CHECK in (`pdf`,`docx`) |
| `content_type` | VARCHAR(100) | yes | | detected, not client-supplied |
| `size_bytes` | INTEGER | yes | | CHECK ≤ 5 242 880 |
| `sha256` | CHAR(64) | yes | | integrity / optional de-duplication |
| `storage_key` | VARCHAR(512) | yes | | S3 object key (random, not derived from filename) |
| `extracted_text` | TEXT | no | | full text; cleared on delete |
| `parse_status` | VARCHAR(16) | yes | | `parsed` (MVP); reserved: `processing`, `failed` |
| `created_at` | TIMESTAMPTZ | yes | | |
| `deleted_at` | TIMESTAMPTZ | no | | soft-delete marker while the purge job removes the S3 object |

#### `cv_profiles`  *(structured extraction; shape provisional, OD-4)*

| Field | Type | Req | Key | Notes |
| --- | --- | --- | --- | --- |
| `cv_id` | UUID | yes | PK, FK → `cvs.id` ON DELETE CASCADE | 1 : 1 |
| `experience` | JSONB | yes | | array of strings, default `[]` |
| `education` | JSONB | yes | | array of strings, default `[]` |
| `projects` | JSONB | yes | | array of strings, default `[]` |
| `extractor_version` | VARCHAR(50) | yes | | which extraction method produced this |
| `created_at` | TIMESTAMPTZ | yes | | |

#### `cv_skills`

| Field | Type | Req | Key | Notes |
| --- | --- | --- | --- | --- |
| `id` | UUID | yes | PK | |
| `cv_id` | UUID | yes | FK → `cvs.id` ON DELETE CASCADE | |
| `name` | VARCHAR(100) | yes | | unique per (`cv_id`, lower(`name`)) |
| `source` | VARCHAR(16) | yes | | e.g. `rules`, `genai` (OD-4) |

#### `interviews`

| Field | Type | Req | Key | Notes |
| --- | --- | --- | --- | --- |
| `id` | UUID | yes | PK | |
| `user_id` | UUID | yes | FK → `users.id` ON DELETE CASCADE | |
| `cv_id` | UUID | no | FK → `cvs.id` ON DELETE SET NULL | kept `NULL` after the CV is deleted |
| `target_role` | VARCHAR(100) | yes | | free text, 3–100 |
| `interview_type` | VARCHAR(10) | yes | | CHECK in (`technical`,`behavioral`,`mixed`) |
| `difficulty` | VARCHAR(12) | yes | | CHECK in (`beginner`,`intermediate`,`advanced`) |
| `question_count` | SMALLINT | yes | | CHECK in (5, 10, 15) |
| `status` | VARCHAR(12) | yes | | CHECK in (`in_progress`,`completed`,`abandoned`) |
| `question_source` | VARCHAR(8) | yes | | `bank` or `genai` (OD-5) |
| `overall_score` | SMALLINT | no | | 0–100, set on completion |
| `created_at` | TIMESTAMPTZ | yes | | |
| `completed_at` | TIMESTAMPTZ | no | | |
| `updated_at` | TIMESTAMPTZ | yes | | |

#### `interview_questions`

| Field | Type | Req | Key | Notes |
| --- | --- | --- | --- | --- |
| `id` | UUID | yes | PK | |
| `interview_id` | UUID | yes | FK → `interviews.id` ON DELETE CASCADE | |
| `position` | SMALLINT | yes | | ≥ 1; **unique with `interview_id`** |
| `text` | TEXT | yes | | |
| `question_type` | VARCHAR(10) | yes | | CHECK in (`technical`,`behavioral`) |
| `ideal_answer` | TEXT | yes | | never returned before evaluation |
| `source` | VARCHAR(8) | yes | | `bank` / `genai` |
| `bank_question_id` | UUID | no | FK → `question_bank.id` ON DELETE SET NULL | only when drawn from the bank |
| `created_at` | TIMESTAMPTZ | yes | | |

#### `answers`

| Field | Type | Req | Key | Notes |
| --- | --- | --- | --- | --- |
| `id` | UUID | yes | PK | |
| `question_id` | UUID | yes | FK → `interview_questions.id` ON DELETE CASCADE, **unique** | one answer per question |
| `answer_text` | TEXT | yes | | 30–1500 chars at write time |
| `char_count` | INTEGER | yes | | |
| `input_mode` | VARCHAR(8) | yes | | `text` (default); `speech` reserved (OD-6) |
| `submitted_at` / `updated_at` | TIMESTAMPTZ | yes | | |

#### `evaluations`

| Field | Type | Req | Key | Notes |
| --- | --- | --- | --- | --- |
| `id` | UUID | yes | PK | |
| `answer_id` | UUID | yes | FK → `answers.id` ON DELETE CASCADE, **unique** | |
| `overall_score` | SMALLINT | yes | | CHECK 0–100 |
| `relevance_score` | SMALLINT | yes | | CHECK 0–100 |
| `clarity_score` | SMALLINT | yes | | CHECK 0–100 |
| `technical_depth_score` | SMALLINT | yes | | CHECK 0–100 |
| `confidence_score` | SMALLINT | yes | | CHECK 0–100 |
| `semantic_similarity` | NUMERIC(5,4) | no | | raw model output, kept for calibration against human ratings; **not** exposed by the API |
| `strengths` | JSONB | yes | | array of 1–3 strings |
| `weaknesses` | JSONB | yes | | array of 1–3 strings |
| `improvement_tip` | TEXT | yes | | |
| `feedback_source` | VARCHAR(8) | yes | | `rules` / `genai` |
| `scoring_version` | VARCHAR(30) | yes | | |
| `model_info` | JSONB | yes | | model names/versions used (embedding, scorer, GenAI) |
| `latency_ms` | INTEGER | no | | for CloudWatch/analysis |
| `created_at` | TIMESTAMPTZ | yes | | |

#### `interview_results`

| Field | Type | Req | Key | Notes |
| --- | --- | --- | --- | --- |
| `interview_id` | UUID | yes | PK, FK → `interviews.id` ON DELETE CASCADE | 1 : 1 |
| `overall_score` | SMALLINT | yes | | duplicate of `interviews.overall_score` written in the same transaction |
| `confidence_score`, `relevance_score`, `clarity_score`, `technical_depth_score`, `communication_score` | SMALLINT | yes | | the five `breakdown` values |
| `additional_strength` | TEXT | yes | | |
| `additional_improvement` | TEXT | yes | | |
| `recommendations` | JSONB | yes | | array of 3 strings |
| `generated_by` | VARCHAR(8) | yes | | `rules` / `genai` |
| `created_at` | TIMESTAMPTZ | yes | | |

#### `user_performance`

| Field | Type | Req | Key | Notes |
| --- | --- | --- | --- | --- |
| `id` | UUID | yes | PK | |
| `user_id` | UUID | yes | FK → `users.id` ON DELETE CASCADE | |
| `skill_key` | VARCHAR(20) | yes | | CHECK in (`communication`,`relevance`,`confidence`,`clarity`,`technical_depth`); **unique with `user_id`** |
| `score` | SMALLINT | yes | | 0–100 |
| `interviews_counted` | INTEGER | yes | | |
| `updated_at` | TIMESTAMPTZ | yes | | |

Maintained inside the E14 transaction by **recomputing from the user's `interview_results`** rather than incrementing, so values cannot drift. For the capstone data volume this table could equally be a view; a table was chosen so the read path of E20 is trivial.

#### `question_bank`  *(reference data; depends on OD-5)*

| Field | Type | Req | Key | Notes |
| --- | --- | --- | --- | --- |
| `id` | UUID | yes | PK | |
| `text` | TEXT | yes | | |
| `question_type` | VARCHAR(10) | yes | | `technical` / `behavioral` |
| `difficulty` | VARCHAR(12) | yes | | |
| `role_tags` | JSONB | yes | | e.g. `["AI Engineer","Data Scientist"]` |
| `ideal_answer` | TEXT | no | | curated reference answer when available |
| `embedding` | vector / BLOB / JSON | no | | storage mechanism **[Open]** (OD-5) |
| `source_note` | VARCHAR(255) | no | | attribution / licence of the source |
| `is_active` | BOOLEAN | yes | | |
| `created_at` | TIMESTAMPTZ | yes | | |

### 15.3 Indexes and constraints

| Purpose | Index / constraint |
| --- | --- |
| History (E19) | `interviews (user_id, status, completed_at DESC)` |
| Question lookup | unique `interview_questions (interview_id, position)` |
| One answer / evaluation / result | unique `answers (question_id)`, `evaluations (answer_id)`, PK `interview_results (interview_id)` |
| Performance upsert | unique `user_performance (user_id, skill_key)` |
| CV list (E08) | `cvs (user_id, created_at DESC) WHERE deleted_at IS NULL` |
| Login | unique `users (email)` |
| Score sanity | CHECK 0–100 on every score column |

### 15.4 Deletion and retention behaviour

| Event | Effect |
| --- | --- |
| Delete CV (E10) | `cvs` row, S3 object, `cv_profiles`, `cv_skills` removed; `interviews.cv_id` → `NULL`; interviews, answers, evaluations and results remain |
| Abandon interview (E13) | status → `abandoned`; rows kept; excluded from history/results/performance |
| Delete user (future) | cascades to everything above |
| Retention period for CVs and answers | **[Open]** (OD-10) |

---

## 16. AI/ML Pipeline

This section assigns every intelligent or computed step to exactly one of four classes so that responsibilities, failure handling and owners are unambiguous. Nothing here is implemented, and no model has been selected or trained.

| Class | Meaning | Typical failure handling |
| --- | --- | --- |
| **[D] Deterministic** | ordinary backend logic with a fixed, testable outcome | bug → `500`; never "retried into a different answer" |
| **[ML] Model** | local model inference (Sentence Transformers, BERT / DistilBERT, later Whisper) | model unavailable → `AI_SERVICE_UNAVAILABLE` (a score must not be invented) |
| **[GenAI] Generative** | external LLM through OpenAI API or Amazon Bedrock | **optional** by the proposal → timeout/invalid output falls back to rules where a fallback exists |
| **[DB] Database** | reads/writes on RDS | `DATABASE_UNAVAILABLE` (503) |

### 16.1 Pipeline steps

"Basis" says where the step comes from: **[Proposal]** explicit in the proposal; **[Recommended]** introduced here; **[Open]** undecided.

| Step | Task | Class | Input → Output | Basis |
| --- | --- | --- | --- | --- |
| **A** | CV file → plain text | [D] | validated PDF/DOCX → `extracted_text` | **[Proposal]** "CVs … converted to text for processing". Library choice is an implementation detail |
| **B** | CV text → structured information (skills, experience, education, projects) | [D] and/or [ML] and/or [GenAI] | `extracted_text` → `cv_skills`, `cv_profiles` | **[Open]** OD-4 — the proposal does not say how structure is extracted |
| **C** | CV + target role + type + difficulty → *n* questions | [ML] retrieval and/or [GenAI] | structured CV, role, config → question texts and types | **[Proposal]** GenAI generates personalized questions; curated banks "used for RAG". Mechanism **[Open]** OD-5 |
| **D** | each question → ideal answer | [GenAI] and/or curated bank | question (+ role, difficulty) → `ideal_answer` (stored, hidden) | **[Proposal]** "ideal-answer suggestions" via GenAI |
| **E** | candidate answer vs ideal answer → semantic similarity | [ML] Sentence Transformers | two texts → embeddings → cosine similarity → `relevance` | **[Proposal]** "semantic similarity scoring of user answers against ideal responses" |
| **F** | answer → `clarity`, `technical_depth`, `confidence` and `overall_score` | [ML] and/or [D] heuristics | answer, question, similarity → four integers 0–100 | **[Proposal]** BERT / DistilBERT are listed for scoring; **method for these three categories is [Open]** OD-8 |
| **G** | scores/features → strengths and weaknesses | [D] rules over [ML] outputs | category scores → 1–3 strengths, 1–3 weaknesses | **[Proposal]** models "identify strengths/weaknesses"; sentence wording **[Recommended]** from a curated template library |
| **H** | answer + scores → improvement tip (and optionally personalized wording of G) | [D] templates; optionally [GenAI] | → `improvement_tip` | **[Recommended]** — the proposal assigns GenAI to questions and ideal answers, *not* explicitly to feedback text |
| **I** | all evaluations → overall score and breakdown | [D] | evaluations → `interview_results` numbers | **[Recommended]** formulas in Section 11 (they mirror the existing frontend) |
| **J** | breakdown → 3 recommendations and 2 highlight strings | [D] rules; optionally [GenAI] | breakdown → text | **[Recommended]** rules by default, GenAI optional |
| **K** | interview results → user skill scores | [D] + [DB] | `interview_results` → `user_performance` | **[Recommended]** |
| **L** | speech → text (Whisper) | [ML] | audio → transcript → `answer_text` | **[Proposal]** listed in roles; **not in the written workflow** — **[Open]** OD-6, future |
| **M** | answer → personalized follow-up question | [GenAI] | answer + context → new question | **[Proposal]** mentioned in the workflow; **not supported by the current UI** (F21), future |

### 16.2 Where each step runs

```
E07  CV upload ───────────────►  A [D]  ─►  B [D/ML/GenAI?]  ─►  [DB] cvs, cv_profiles, cv_skills

E11  Create interview ────────►  [DB] load CV
                                 C [ML retrieval and/or GenAI]  ─►  n questions
                                 D [GenAI and/or curated bank]  ─►  n ideal answers
                                 [DB] interviews, interview_questions (ideal_answer hidden)

E15  Submit answer ───────────►  [D] validate  ─►  [DB] answers

E16  Evaluate answer ─────────►  [DB] read answer + ideal answer
                                 E [ML] similarity  ─►  F [ML/D] scores
                                 G [D] strengths/weaknesses  ─►  H [D, optional GenAI] tip
                                 [DB] evaluations

E14  Complete interview ──────►  [DB] read evaluations
                                 I [D] aggregate  ─►  J [D, optional GenAI] recommendations
                                 [DB] interview_results, interviews, user_performance (one transaction)
```

### 16.3 Question source: the GenAI-optional consequence

The proposal calls the GenAI layer **optional** and also lists curated question banks "used for RAG". Together they imply two valid ways to produce questions. The backend should hide the choice behind one interface and a configuration value (`QUESTION_SOURCE`), recorded per interview in `interviews.question_source`:

| Mode | How questions and ideal answers are produced | Needs GenAI? |
| --- | --- | --- |
| `bank` | rank curated `question_bank` entries by role, type, difficulty and similarity to the CV's skills (embeddings, ML); use the bank's curated ideal answers | no |
| `genai` | prompt the LLM with a minimised CV summary, role, type, difficulty (optionally grounded in retrieved bank entries — RAG) | yes |

Which mode ships first, and whether a RAG layer is required, is **[Open]** (OD-3, OD-5). The API contract is identical in both modes.

### 16.4 Scoring contract (what the model layer must return)

The API and frontend depend only on this contract, not on how the numbers are produced:

- `relevance`, `clarity`, `technical_depth`, `confidence`, `overall_score` are integers in 0–100, higher is better.
- `strengths` and `weaknesses` each contain 1–3 short sentences; `improvement_tip` is one sentence.
- Output is deterministic for a given `scoring_version` and input (re-evaluating must not change a stored result).

**Interim baseline [Recommended — to be replaced or calibrated].**

| Item | Interim approach |
| --- | --- |
| `relevance` | cosine similarity between answer and ideal-answer embeddings, mapped to 0–100 by a calibration curve; a low similarity to the *question* is an off-topic guard |
| `clarity`, `technical_depth`, `confidence` | transparent feature heuristics (length relative to a target, structure markers, concrete figures, named technologies overlapping with CV and question, hedging language) until labelled data justifies a fine-tuned DistilBERT/BERT model |
| `overall_score` | weighted mean of the four categories with weights held in configuration (initially equal); **the real formula is [Open]** (OD-8) |
| Calibration | the proposal's metric — correlation between the AI score and human-rated benchmarks — is the acceptance test; collect human ratings for a benchmark set, compute the correlation (for example Spearman), tune the mapping, bump `scoring_version` |
| Distribution | the UI's labels (≥ 88 Excellent, ≥ 78 Strong) assume scores spread across the range; raw cosine similarities usually cluster, so calibration must stretch them |

### 16.5 GenAI usage rules (OpenAI API or Amazon Bedrock — OD-3)

| Rule | Detail |
| --- | --- |
| Provider-agnostic adapter | one internal interface (`generate_questions`, `write_feedback`, `write_recommendations`); provider and model are configuration, not code paths in endpoints |
| Structured output | request JSON and validate it against a schema; one retry on invalid output; then fallback or `AI_SERVICE_UNAVAILABLE` |
| Timeouts | per-call timeout shorter than the endpoint budget; total synchronous work must fit the gateway limit (Section 20) |
| Fallback | step H, J: rule-based text. Step C/D: if mode is `genai` and the call fails, fall back to `bank` when it is populated, else error |
| Prompt injection | CV text and answers are **untrusted**: delimit them, instruct the model to ignore instructions inside them, never let output trigger actions, validate output shape and length |
| Data minimisation | send the minimum: strip name, email, phone and address from CV text before an external call (**[Recommended]**); never send tokens, keys or other users' data |
| Cost control | cap tokens per call; answers are already limited to 1500 characters; per-user rate limits (Section 19); cache bank-derived ideal answers |
| Provider data terms | review the chosen provider's retention and training-use terms before sending CV content (OD-10) |
| Logging | log latency, model name and token counts; never log prompts containing CV text or answers |

### 16.6 Model serving

- **[Recommended]** Load embedding and scoring models once at FastAPI start-up inside the same process; expose readiness through `/health` (E22) so the service is not marked ready before models load.
- Record model identifiers and versions in `evaluations.model_info` and the configuration version in `scoring_version`.
- Model choice (for example a small Sentence Transformers model, DistilBERT vs BERT) belongs to the ML owner; **none is decided here**.
- Whisper (step L) is much heavier than the text models and may need a separate instance size — a reason to keep it out of the MVP (Section 22).

### 16.7 Responsibility matrix per operation

| Operation | Deterministic | ML model | GenAI | Database |
| --- | --- | --- | --- | --- |
| E07 upload CV | validation, text extraction | (maybe) skill extraction | (maybe, OD-4) | `cvs`, `cv_profiles`, `cv_skills`, S3 |
| E11 create interview | validation, type mix, uniqueness | question retrieval (bank mode) | questions, ideal answers (genai mode) | `interviews`, `interview_questions` |
| E15 submit answer | length rules | — | — | `answers` |
| E16 evaluate | feedback selection, rounding | similarity, scoring | optional wording | `evaluations` |
| E14 complete | aggregation, formulas | — | optional recommendation wording | `interview_results`, `user_performance`, `interviews` |
| E18–E21 reads | ordering, formatting | — | — | reads only |

---

## 17. Request/Response Schemas

### 17.1 Enumerations

| Name | Values (API) | Frontend display value |
| --- | --- | --- |
| `interview_type` | `technical`, `behavioral`, `mixed` | `Technical`, `Behavioral`, `Mixed` |
| `difficulty` | `beginner`, `intermediate`, `advanced` | `Beginner`, `Intermediate`, `Advanced` |
| `question_type` | `technical`, `behavioral` | `Technical`, `Behavioral` |
| `interview_status` | `in_progress`, `completed`, `abandoned` | history shows `Completed` only |
| `question_state` | `pending`, `answered`, `evaluated` | — |
| `question_count` | `5`, `10`, `15` | same |
| `feedback_source` / `generated_by` | `rules`, `genai` | not displayed |
| `skill_key` | `communication`, `relevance`, `confidence`, `clarity`, `technical_depth` | `Communication`, `Relevance`, `Confidence`, `Clarity`, `Technical Depth` |

### 17.2 Shared objects

| Schema | Fields |
| --- | --- |
| **User** | `id` uuid · `name` string · `email` string · `created_at` timestamp |
| **CV** | `id` uuid · `original_filename` string · `extension` `pdf`\|`docx` · `size_bytes` int · `parse_status` string · `created_at` timestamp |
| **CVExtracted** | `skills` string[] · `experience` string[] · `education` string[] · `projects` string[] |
| **InterviewConfig** | `cv_id` uuid · `target_role` string · `interview_type` enum · `difficulty` enum · `question_count` int |
| **Question** | `id` uuid · `position` int · `text` string · `type` enum (+ `state` in E12) |
| **Answer** | `id` uuid · `interview_id` uuid · `question_id` uuid · `answer_text` string · `char_count` int · `input_mode` string · `submitted_at` / `updated_at` timestamp |
| **CategoryScores** | `relevance` · `clarity` · `technical_depth` · `confidence` — integers 0–100 |
| **Evaluation** | `id` · `question_id` · `overall_score` int · `category_scores` CategoryScores · `strengths` string[1..3] · `weaknesses` string[1..3] · `improvement_tip` string · `ideal_answer` string · `feedback_source` enum · `scoring_version` string · `created_at` timestamp |
| **InterviewSummary** (`interview` in results) | `id` · `completed_at` · `target_role` · `interview_type` · `difficulty` · `question_count` · `overall_score` · `status` |
| **Breakdown** | `confidence` · `relevance` · `clarity` · `technical_depth` · `communication` — integers 0–100 |
| **Results** | `interview` InterviewSummary · `breakdown` Breakdown · `additional_strength` string · `additional_improvement` string · `recommendations` string[3] · `generated_by` enum · `items[]` {`position`, `question` {id,text,type}, `answer_text`, `evaluation` Evaluation} |
| **HistoryItem** | `id` · `completed_at` · `target_role` · `interview_type` · `difficulty` · `question_count` · `overall_score` · `status` |
| **SkillScore** | `key` skill_key · `label` string · `score` int |
| **Page<T>** | `items` T[] · `total` int · `limit` int · `offset` int |
| **Error** | see Section 18 |

### 17.3 Mapping API shapes to the frontend's current shapes

The adapter inside `api.js` (Section 24) performs these conversions so that **no component or context needs to change** shape expectations.

| Frontend shape (today) | Built from the API | Rule |
| --- | --- | --- |
| `meta.id` | `id` | |
| `meta.date` | `completed_at` | format as `Sep 24, 2026` (`en-US`, month short, day numeric, year numeric) |
| `meta.role` / `.type` / `.diff` / `.n` / `.score` | `target_role` / `interview_type` / `difficulty` / `question_count` / `overall_score` | enums capitalised |
| `meta.status` | `status` | `completed` → `Completed` |
| `question {id?, text, type}` | `Question` | `type` capitalised; **keep `id`** (new, F2) |
| `ev.score` | `overall_score` | |
| `ev.cats` | `category_scores` | keys in this order: `Relevance`, `Clarity`, `Technical Depth`, `Confidence` |
| `ev.strengths` / `ev.weaknesses` / `ev.tip` / `ev.ideal` | `strengths` / `weaknesses` / `improvement_tip` / `ideal_answer` | |
| `results.items[i]` = `{q, ev}` | `items[i]` | `q` ← `question`, `ev` ← `evaluation` |
| `results.extraStrength` / `.extraImprovement` | `additional_strength` / `additional_improvement` | |
| `results.recommendations` | `recommendations` | |
| `skills` (object) | `skills[]` | build `{label: score}` preserving array order (F7) |
| `cvFile` | `CV` | `{ name: original_filename, ext: extension.toUpperCase(), size: "<n> KB", id }` |
| `user` | `User` | `{ name, email }` (+ `id`) |

Example — the adapter output for one evaluation is exactly the object the UI already renders:

```json
{
  "score": 82,
  "cats": { "Relevance": 86, "Clarity": 79, "Technical Depth": 77, "Confidence": 81 },
  "strengths": ["Clearly explained the technical approach.", "Demonstrated practical experience.", "Provided relevant examples."],
  "weaknesses": ["The answer was brief; add more depth and detail.", "Could quantify the project impact more clearly.", "The answer could be more structured."],
  "tip": "Use the STAR method (Situation, Task, Action, Result) and close with a measurable outcome.",
  "ideal": "At my last internship I built a ticket-routing classifier…"
}
```

### 17.4 Validation limits (server must match or exceed the UI)

| Input | UI today | Server rule |
| --- | --- | --- |
| CV extension | `pdf`, `docx` by name | `pdf`, `docx` by name **and** content signature |
| CV size | ≤ 5 × 1024 × 1024 bytes | same, enforced while streaming |
| Target role | ≥ 3 chars when typed; no maximum | trimmed 3–100 |
| Interview type / difficulty / count | fixed chips | strict enums; count ∈ {5,10,15} |
| Answer | trimmed ≥ 30; raw ≤ 1500 | trimmed 30–1500 code points |
| Profile name | trimmed ≥ 2 | trimmed 2–100 |
| Profile email | `^\S+@\S+\.\S+$` | RFC-style email validation, ≤ 254 chars |

---

## 18. Error Handling

### 18.1 Envelope

Success responses are plain resources. **All** failures use one envelope:

```json
{
  "error": {
    "code": "CV_UNREADABLE",
    "message": "We couldn't read any text from this CV. Please upload a text-based PDF or DOCX.",
    "details": [],
    "retryable": false,
    "request_id": "req_7f3a91c2"
  }
}
```

| Field | Type | Notes |
| --- | --- | --- |
| `code` | string | stable, machine-readable, `UPPER_SNAKE_CASE`; the frontend branches on this |
| `message` | string | safe to show to the user; never contains stack traces, SQL, paths or provider error text |
| `details` | array | optional field-level info: `{ "field": "answer_text", "issue": "min_length", "limit": 30 }` |
| `retryable` | boolean | `true` when the same request may succeed later (AI/DB/transient failures) |
| `request_id` | string | also sent as `X-Request-ID`; correlates with CloudWatch logs |

A `success: false` flag is omitted on purpose: the HTTP status already says so and an extra boolean could contradict it.

### 18.2 Error catalog

| Code | HTTP | When | Endpoints |
| --- | --- | --- | --- |
| `VALIDATION_ERROR` | 422 | malformed body/query/path (generic) | all |
| `UNAUTHORIZED` | 401 | missing or invalid credentials/token | all protected |
| `TOKEN_EXPIRED` | 401 | access token expired — client should refresh | all protected, E03 |
| `TOKEN_INVALID` | 401 | refresh token revoked/invalid | E03 |
| `INVALID_CREDENTIALS` | 401 | wrong email or password | E02 |
| `FORBIDDEN` | 403 | authenticated but not permitted (rare; foreign resources use 404) | — |
| `EMAIL_ALREADY_REGISTERED` | 409 | registration with an existing email | E01 |
| `EMAIL_ALREADY_IN_USE` | 409 | profile email belongs to another user | E06 |
| `UNSUPPORTED_FILE_TYPE` | 415 | not a genuine PDF/DOCX | E07 |
| `FILE_TOO_LARGE` | 413 | CV larger than 5 MB | E07 |
| `CV_UNREADABLE` | 422 | corrupt, encrypted, no extractable text, or below minimum text length | E07 |
| `CV_REQUIRED` | 422 | `cv_id` missing/null when creating an interview | E11 |
| `CV_NOT_FOUND` | 404 | CV id unknown, deleted, or not owned by the caller | E09, E10, E11 |
| `INVALID_INTERVIEW_CONFIG` | 422 | role/type/difficulty/count invalid (field-level `details`) | E11 |
| `INTERVIEW_NOT_FOUND` | 404 | unknown or not owned | E12–E18 |
| `QUESTION_NOT_FOUND` | 404 | question not in this interview | E15–E17 |
| `ANSWER_NOT_FOUND` | 404 | evaluating a question with no stored answer | E16 |
| `EVALUATION_NOT_FOUND` | 404 | fetching an evaluation that does not exist yet | E17 |
| `ANSWER_EMPTY` | 422 | empty or whitespace-only answer | E15 |
| `ANSWER_TOO_SHORT` | 422 | trimmed length < 30 | E15 |
| `ANSWER_TOO_LONG` | 422 | length > 1500 | E15 |
| `ANSWER_ALREADY_EVALUATED` | 409 | replacing an answer that has an evaluation | E15 |
| `INTERVIEW_NOT_ACTIVE` | 409 | action on a completed or abandoned interview | E13–E16 |
| `INTERVIEW_INCOMPLETE` | 409 | completing before every question is evaluated | E14 |
| `RESULTS_NOT_AVAILABLE` | 409 | results requested for a non-completed interview | E18 |
| `RATE_LIMITED` | 429 | too many requests (`Retry-After` header) | all, especially E07, E11, E16 |
| `AI_SERVICE_UNAVAILABLE` | 503 | ML model or GenAI provider failed with no fallback | E11, E16 |
| `AI_SERVICE_TIMEOUT` | 504 | AI step exceeded its budget with no fallback | E11, E16 |
| `STORAGE_UNAVAILABLE` | 503 | S3 failure | E07, E10 |
| `DATABASE_UNAVAILABLE` | 503 | database connection/transaction failure (no details exposed) | all |
| `INTERNAL_ERROR` | 500 | unexpected server error | all |

### 18.3 Examples

```json
{ "error": { "code": "UNSUPPORTED_FILE_TYPE", "message": "Unsupported format. Please upload a PDF or DOCX file.",
             "details": [], "retryable": false, "request_id": "req_1c4e88d0" } }
```

```json
{ "error": { "code": "ANSWER_TOO_SHORT", "message": "Please write at least 30 characters so the AI can evaluate your answer.",
             "details": [ { "field": "answer_text", "issue": "min_length", "limit": 30 } ],
             "retryable": false, "request_id": "req_a93b02f7" } }
```

```json
{ "error": { "code": "AI_SERVICE_UNAVAILABLE", "message": "The evaluation service is temporarily unavailable. Please try again.",
             "details": [], "retryable": true, "request_id": "req_5d2e7b19" } }
```

```json
{ "error": { "code": "INTERVIEW_INCOMPLETE", "message": "Every question must be answered and evaluated before finishing.",
             "details": [ { "field": "questions", "issue": "unevaluated_positions", "positions": [4, 5] } ],
             "retryable": false, "request_id": "req_e08f4c63" } }
```

### 18.4 Frontend handling guidance

| Situation | Today (F13) | Target behaviour |
| --- | --- | --- |
| Any failure | fixed generic string per screen | show `error.message` (the server messages are written for users), fall back to the generic string if the body is not an error envelope |
| `TOKEN_EXPIRED` | not handled | call E03 once, retry the original request once |
| `UNAUTHORIZED`, `TOKEN_INVALID` | not handled | clear session, go to sign-in |
| `retryable: true` | no retry hint | show the existing "try again" state; answer text is already preserved by the UI |
| `RATE_LIMITED` | not handled | respect `Retry-After` |
| Network error / timeout | none | add a client-side timeout so a stalled call becomes a normal error |

---

## 19. Security Requirements

Requirements only — none is implemented. IDs allow tracing in reviews.

### 19.1 Authentication and authorization

| ID | Requirement |
| --- | --- |
| S-01 | Every endpoint except register, login, refresh and health requires a valid access token (final mechanism: OD-1). |
| S-02 | **Object-level authorization:** every query on CVs, interviews, questions, answers, evaluations and results is filtered by the authenticated `user_id`. Foreign or unknown IDs return `404`, never `403`, so IDs cannot be probed. |
| S-03 | Never trust client-supplied scores or aggregates. E14 ignores the `items` the frontend currently sends (F4); scores are produced only server-side. |
| S-04 | If passwords are used: argon2id or bcrypt, per-user salt, never logged or returned; login responses must not reveal whether an email exists. |
| S-05 | Rate limiting per user and per IP, strictest on login, E07 (parsing cost), E11 and E16 (AI cost). |

### 19.2 CV file handling

| ID | Requirement |
| --- | --- |
| S-06 | Allowed types: PDF and DOCX only. Reject `.doc`, `.docm`, `.dotm` and anything else. |
| S-07 | Validate the **content signature** (PDF header; DOCX is a ZIP containing `[Content_Types].xml` and `word/document.xml`), not just the extension or the client's `Content-Type`. |
| S-08 | Maximum size 5 MB, enforced while streaming (abort early) and again at the gateway tier; the API Gateway ceiling is 10 MB (Section 20). |
| S-09 | Defend against decompression bombs and malicious structure: cap uncompressed DOCX size and entry count; reject encrypted PDFs; apply a parse timeout; parse in a constrained context. |
| S-10 | Sanitise the filename; store under a random S3 key; never build paths from user input; never execute or serve uploaded files back to browsers. |
| S-11 | Antivirus scanning of uploads is a **recommended hardening** (future if not in MVP). |

### 19.3 Input validation and untrusted text

| ID | Requirement |
| --- | --- |
| S-12 | Validate every request with strict typed schemas (enums, lengths, formats) and reject unknown fields where feasible. Limit JSON body size. |
| S-13 | All SQL through parameterised queries / an ORM. |
| S-14 | CV text and answers are **untrusted input to language models** (prompt injection). Delimit them in prompts, validate model output against schemas, and never let model output drive actions (Section 16.5). |
| S-15 | Responses are JSON only; stored free text is returned as data, never as markup. The frontend renders it as text (React escapes by default). |

### 19.4 Secrets and configuration

| ID | Requirement |
| --- | --- |
| S-16 | Secrets (database credentials, JWT signing key, OpenAI/Bedrock credentials) come from environment variables or an AWS secret store and are never committed. The frontend repository already ignores `.env`. |
| S-17 | AI provider keys exist **only on the backend**; the frontend must never receive or embed them. |
| S-18 | Separate configuration and credentials per environment (development / production); rotate keys on exposure. |

### 19.5 Transport, CORS and headers

| ID | Requirement |
| --- | --- |
| S-19 | HTTPS only; TLS terminates at API Gateway (or the chosen edge). |
| S-20 | CORS allow-list limited to the deployed frontend origin(s) plus `http://localhost:5173` in development; no wildcard with credentials; allow only the methods and headers in this spec. |
| S-21 | If the refresh token is a cookie: `HttpOnly; Secure`, narrow `Path`, appropriate `SameSite`, and a CSRF review (OD-1). |
| S-22 | Add `X-Content-Type-Options: nosniff` and a request-size limit on all responses/requests. |

### 19.6 Data protection and privacy

| ID | Requirement |
| --- | --- |
| S-23 | CVs and answers are personal data. S3 buckets are private with server-side encryption and public access blocked; RDS is encrypted at rest and reachable only from the application's security group. |
| S-24 | Never log CV text, answers, tokens, passwords or full prompts; log IDs, sizes, durations and error codes. |
| S-25 | Minimise what is sent to an external LLM (strip contact details, send only needed text) and review provider retention/training terms (OD-10). |
| S-26 | Users can delete a CV (E10). A full account/data deletion path and retention periods are required before real users are onboarded (OD-10, Section 22). |
| S-27 | Error responses never expose internals (stack traces, SQL, file paths, provider messages). |

### 19.7 Operational security

| ID | Requirement |
| --- | --- |
| S-28 | Structured logging with `request_id` to CloudWatch; alarms on error rate, latency and AI failure rate. |
| S-29 | RDS in a private subnet; EC2 security group exposes only what the gateway needs; SSH restricted. |
| S-30 | If API Gateway forwards to a public EC2 address, the backend must verify a shared origin secret header so that the API cannot be reached by bypassing the gateway (Section 20). |

---

## 20. AWS Architecture

The proposal names five AWS services (EC2, S3, RDS, API Gateway, CloudWatch) in the Cloud/DevOps role and the workflow. This section places each one and **does not add other AWS services to the baseline**. Nothing is deployed.

### 20.1 Service placement

| Service | Role in this system | Basis |
| --- | --- | --- |
| **EC2** | runs the FastAPI application (and, in the MVP, the in-process ML models) | **[Proposal]** (Cloud/DevOps role) |
| **RDS** | PostgreSQL or MySQL holding users, CV metadata, interviews, questions, answers, evaluations, results, performance | **[Proposal]** (§3 Tech Stack); engine **[Open]** OD-2 |
| **S3** | private bucket for uploaded CV files (database keeps only the object key); optionally model artifacts | **[Proposal]** (listed in roles); usage for CV files **[Recommended]** |
| **API Gateway** | public HTTPS entry point in front of FastAPI: TLS, throttling, request-size ceiling | **[Proposal]**; type **[Open]** OD-12 |
| **CloudWatch** | logs, metrics, alarms and dashboards for system performance | **[Proposal]** §4 step 4 |

### 20.2 Baseline topology

```
 Browser ── React build (hosting: OD-11)
    │
    │  HTTPS  /api/v1/*
    ▼
 ┌──────────────────┐   throttling · TLS · 10 MB payload ceiling
 │   API Gateway    │───────────────────────────────┐
 └────────┬─────────┘                               │ access logs, metrics
          │ HTTP proxy integration                  ▼
          ▼                                   ┌────────────┐
 ┌──────────────────────────────┐             │ CloudWatch │◄── app logs (JSON, request_id)
 │ EC2 — FastAPI (Uvicorn)       │────────────►│ logs · metrics · alarms
 │  routers · services           │             └────────────┘
 │  ML models (in-process)       │
 │  GenAI adapter ───────────────┼──► OpenAI API / Amazon Bedrock   (OD-3)
 └───────┬───────────────┬──────┘
         │               │
         ▼               ▼
   ┌───────────┐   ┌───────────┐
   │ RDS (SQL) │   │ S3 bucket │   private, encrypted, CV files only
   │ private   │   └───────────┘
   │ subnet    │
   └───────────┘
```

### 20.3 API Gateway constraints that shape the design

Verified against the AWS API Gateway quota documentation (October 2026; re-check before deployment):

| Limit | REST API | HTTP API |
| --- | --- | --- |
| Integration timeout | 29 seconds by default; can be raised above 29 s, but this may require lowering the account's regional throttle quota | 30 seconds maximum (not adjustable) |
| Payload size | 10 MB (not adjustable) | 10 MB (not adjustable) |

Consequences:

- **Uploads:** the 5 MB CV limit sits safely under the 10 MB ceiling, so CVs can be sent through the gateway as multipart (no presigned-URL flow is needed for the MVP).
- **Synchronous AI calls:** E11 (question + ideal-answer generation) and E16 (evaluation) run inside one HTTP request. Each must complete well under ~25 seconds including network, model and database time. If measurements show otherwise (large GenAI calls, slow CPU inference), the fallback is an asynchronous job pattern (`202 Accepted` + status endpoint) — **not in the MVP**, listed in Section 22. The frontend's current spinner-based screens would need a polling step for that (OD-13).
- **Type choice (OD-12):** HTTP API is simpler and cheaper; REST API offers usage plans, request validation and AWS WAF integration. The proposal says only "API Gateway".

### 20.4 Reaching EC2 from API Gateway

| Approach | Notes |
| --- | --- |
| **Baseline:** HTTP proxy integration to the EC2 instance's address | simplest. The instance is then internet-reachable, so it must verify a shared **origin-secret header** that API Gateway adds (S-30) and restrict everything else |
| Hardened (optional): private integration | API Gateway reaches EC2 inside the VPC through a VPC link and an internal load balancer. This introduces a load balancer, which is **not in the proposal's list** — mark as optional hardening, not baseline |

### 20.5 Component notes

**EC2.** One instance is sufficient for a capstone. Run FastAPI under Uvicorn; load models at start-up (Section 16.6) and report readiness through E22. Instance size depends on the chosen models (OD-13). Whisper, if added later, may need a larger instance or separate hosting.

**RDS.** Private subnet; security group allows connections only from the EC2 security group; automated backups on; connection pooling in the application; credentials from environment/secret store (S-16).

**S3.** One private bucket, public access blocked, server-side encryption, object keys generated by the server (S-10), lifecycle rule for objects whose CV was deleted (E10 removes immediately; the rule is a safety net). The browser never reads CV objects directly.

**CloudWatch.**

| Signal | Purpose |
| --- | --- |
| Application logs (structured JSON with `request_id`, user id, route, status, duration; **no CV text or answers**) | debugging and audit |
| Metrics: request count/latency/errors per route; `evaluation_latency_ms`; GenAI call latency and failure count; CV parse failures | "AWS CloudWatch monitoring system performance" (proposal) |
| Alarms: 5xx rate, p95 latency of E11/E16, AI failure rate, RDS connections/CPU | operational response |
| `/health` (E22) | readiness/liveness checks |

### 20.6 Not part of the baseline (mentioned only so nobody assumes them)

Amazon Cognito, Secrets Manager, CloudFront, an Application/Network Load Balancer, Lambda, SQS/job queues and a vector database service are **not** in the proposal. They may become sensible later (Section 22) but are not required by this design.

### 20.7 Configuration surface (names are suggestions)

| Setting | Used for |
| --- | --- |
| `DATABASE_URL` | RDS connection |
| `S3_BUCKET`, `AWS_REGION` | CV storage |
| `CORS_ORIGINS` | allow-list (S-20) |
| `MAX_CV_BYTES` (5 242 880) | upload ceiling |
| `QUESTION_SOURCE` (`bank` \| `genai`) | Section 16.3 |
| `GENAI_PROVIDER`, `GENAI_MODEL` + credentials | only if GenAI is enabled |
| `SCORING_VERSION`, category weights | Section 16.4 |
| `JWT_SECRET`, token lifetimes | only if OD-1 = option A |
| `ORIGIN_SECRET` | S-30 |

The frontend counterpart is `VITE_API_BASE_URL` (already listed in `.env.example`).

---

## 21. MVP Scope

Goal: the core workflow end to end — **CV → target role → interview → answers → evaluation → feedback → results → history** — with the existing frontend.

### 21.1 Included in the first working version

| Area | Included |
| --- | --- |
| Endpoints | all **9 Core** (E06, E07, E11, E14, E15, E16, E18, E19, E20) + **E05** (current user), **E10** (delete CV), **E22** (health) + **E01–E04** if OD-1 selects login = **16 endpoints** |
| Data | `users`, `cvs`, `cv_profiles`, `cv_skills`, `interviews`, `interview_questions`, `answers`, `evaluations`, `interview_results`, `user_performance` (+ `refresh_tokens` if OD-1 = A; `question_bank` if `bank` mode) |
| AI/ML | CV text extraction; Sentence-Transformers-based semantic score; interim category scoring (Section 16.4); rule-based strengths/weaknesses/tip/recommendations; **at least one** question source (`bank` or `genai`) working |
| GenAI | optional per the proposal. If included in the first version: question and ideal-answer generation only; feedback wording stays rule-based with GenAI as an enhancement |
| AWS | one EC2 instance, one RDS instance, one S3 bucket, API Gateway, CloudWatch logs and basic alarms |
| Security | S-01–S-10, S-12–S-13, S-16–S-20, S-23–S-24, S-27, S-30 |
| Frontend | adapter swap behind `api.js` plus changes FC-1 to FC-8 (Section 24) |

### 21.2 Deferred within the MVP phase (second iteration — "Recommended")

E08/E09 (CV list/detail), E12 (resume state), E13 (abandon), E17 (fetch evaluation), E21 (summary). They improve robustness (refresh recovery, cleanup, no client-side aggregation) but the first demo works without them. Total **6 endpoints**.

### 21.3 Explicitly **not** in the MVP

Whisper / speech answers · dynamic follow-up questions · job-description input · web-scraped job postings and a full RAG corpus · asynchronous job processing · account deletion and data export · email verification / password reset · antivirus scanning · admin tools for the question bank · multi-language support · fine-tuning models on human-rated data.

---

## 22. Future Enhancements

| Enhancement | Notes / sketch | Relates to |
| --- | --- | --- |
| **Speech answers (Whisper)** | add `POST /api/v1/transcriptions` (multipart audio ≤ gateway limit) returning `{ "text": "…" }`; the user confirms the transcript, then E15 stores it with `input_mode: "speech"`. UI needs a recorder | OD-6, F22, step L |
| **Dynamic follow-up questions** | `POST /interviews/{id}/questions/{qid}/follow-up` generating a new question from the user's answer; the UI's fixed `n` and progress bar would need to change | F21, step M |
| **Job-description input** | optional `job_description` (string) on E11, stored in `interviews`, used by steps C/D | OD-7, F23 |
| **Full RAG** over curated resources and scraped job postings | offline ingestion pipeline + vector storage; retrieval in step C/D | OD-5 |
| **Async processing** | `202 Accepted` with `GET /jobs/{id}`; UI polls. Needed only if sync calls approach the gateway timeout | OD-13, Section 20.3 |
| **Account and data deletion** | `DELETE /users/me` removing all user data (replaces the demo-only "Reset demo data") | OD-9, OD-10, F11 |
| **Delete a past interview** | `DELETE /interviews/{id}` | — |
| **Email verification, password reset** | only if OD-1 = option A | OD-1 |
| **Direct-to-S3 uploads** | presigned URLs, only if CV size limits grow beyond the gateway ceiling | S-08 |
| **Antivirus scanning** | scan uploads before parsing | S-11 |
| **Model improvement** | fine-tune DistilBERT/BERT heads on human-rated answers; track correlation with human ratings | OD-8 |
| **Server-side breakdown ranking** | return strengths/improvement lists from the server instead of client-side ranking | Section 2.6 |
| **Streaming feedback** | stream evaluation text to the UI | step H |
| **Admin tooling** | manage `question_bank` content | OD-5 |

---

## 23. Open Decisions / Questions

Only items that the proposal or frontend genuinely leave unresolved. Each lists what it blocks so the team can order the discussions.

### OD-1 — Authentication method
- **Why open:** the proposal never mentions authentication; the UI has only a "Sign in as Alex" shortcut (F10).
- **Options:** (A) email + password with JWT access/refresh tokens; (B) managed identity provider such as Cognito (not in the proposal); (C) no login for the capstone demo.
- **Sub-questions:** refresh token in cookie vs response body; whether changing email requires verification.
- **Recommended default:** A.
- **Blocks:** E01–E06, S-01, S-21, FC-4. All other endpoints only assume "an authenticated user".

### OD-2 — PostgreSQL or MySQL
- **Why open:** proposal says "PostgreSQL / MySQL, hosted on AWS RDS".
- **Effect:** type mapping (Section 15), JSON and UUID handling, and the vector-search options in OD-5.
- **Blocks:** database creation, migrations.

### OD-3 — GenAI provider, model, and whether GenAI is in the first release
- **Why open:** "OpenAI API / Amazon Bedrock (GenAI, optional)"; no model named.
- **Options:** OpenAI; Bedrock (stays inside AWS); none in the first release (`bank` mode).
- **Blocks:** step C/D implementation, `GENAI_*` configuration, data-privacy review (OD-10).

### OD-4 — How structured CV information is extracted
- **Why open:** the proposal says CVs are "converted to text"; it does not say how skills/experience are extracted, or whether GenAI is used for it.
- **Options:** keyword/taxonomy matching; embedding-based matching; GenAI extraction; a combination.
- **Blocks:** shape of `extracted` and `cv_profiles` (currently provisional), question personalization quality.

### OD-5 — Question source and the role of RAG
- **Why open:** the proposal lists "curated interview question banks and career resources used for RAG" and the "LLMs & RAG" track, but also marks GenAI optional and names no vector store or retrieval design.
- **Options:** `bank` retrieval only; `genai` only; GenAI grounded by retrieved bank entries (RAG). Vector storage: none / a PostgreSQL vector extension / an external vector store.
- **Blocks:** `question_bank` design, step C/D, content-curation work.

### OD-6 — Is speech input (Whisper) in the first release?
- **Why open:** Whisper appears in the ML engineer's role and the value proposition ("speech/text evaluation"), but the written workflow says answers are given "via text", and the UI is text-only (F22).
- **Recommended default:** not in the MVP.
- **Blocks:** a transcription endpoint, recorder UI, instance sizing.

### OD-7 — Is job-description input required?
- **Why open:** job descriptions are listed among data sources, but no workflow step takes one and the UI has no field (F23).
- **Recommended default:** not in the MVP; reserve an optional field later.

### OD-8 — Exact scoring and "confidence score" definition
- **Why open:** the proposal says the models "compute a confidence score" and validates it by correlation with human-rated benchmarks, but gives no formula. It also does not say how clarity, technical depth and confidence are derived (only semantic similarity is described). The UI uses "confidence" both as the overall figure on the dashboard and as a per-answer category (F16).
- **Questions:** how each category is computed; the overall formula/weights; the calibration dataset; what the user-facing term for the overall figure should be.
- **Blocks:** step F, `scoring_version`, E16/E14 numbers, label thresholds (88/78).

### OD-9 — Profile edge cases
- **Why open:** email is editable and "Reset demo data" exists in the UI (F11), but neither maps cleanly onto real accounts.
- **Questions:** may email change without verification? Is "Reset demo data" removed in production, or replaced by account/data deletion?

### OD-10 — Data retention, consent and provider data handling
- **Why open:** the proposal does not discuss privacy; CVs and answers are personal data and may be sent to an external LLM.
- **Questions:** retention period for CVs and answers; consent wording; provider retention/training terms; deletion guarantees.
- **Blocks:** S-25, S-26, account-deletion work.

### OD-11 — Where the React build is hosted
- **Why open:** the proposal does not say how the frontend is served.
- **Options:** the same EC2 instance behind a web server; S3 static hosting (HTTPS needs an additional service); another host. Affects CORS origins.

### OD-12 — API Gateway type and how it reaches EC2
- **Why open:** proposal says only "API Gateway".
- **Options:** HTTP API vs REST API (Section 20.3); public EC2 with origin secret vs private integration (Section 20.4).

### OD-13 — Latency budgets, sync vs async, and instance sizing
- **Why open:** depends on the chosen models (OD-3, OD-8) and measured performance.
- **Questions:** target and hard limit for E11 and E16; whether an async job pattern is needed; EC2 instance size.

### 23.2 Recommendations in this document that the team may override

| Recommendation | Section |
| --- | --- |
| `/api/v1` base path, `snake_case`, lowercase enums, UUID ids | 4.1 |
| No `success` wrapper; uniform `error` envelope | 4.1, 18 |
| Evaluation as `POST` (idempotent) plus `GET` | 10 |
| `PUT` answer (upsert) | 9 |
| Ideal answers generated at question-creation time and hidden until evaluated | 8 |
| `QUESTION_SOURCE` switch (`bank` / `genai`) | 16.3 |
| Rule-based feedback text with GenAI optional | 16.1 (H, J) |
| Interim scoring baseline | 16.4 |
| `user_performance` as a recomputed table | 15.2 |
| 15-minute access token, hashed rotating refresh token | 5.2 |
| In-process model loading | 16.6 |
| Strip contact details before sending CV text to an external LLM | 16.5 |

---

## 24. Frontend Integration Plan

### 24.1 Principles

1. **Keep the `api` object and its function names.** Components and contexts keep calling `api.uploadCV()`, `api.startInterview()`, etc.
2. **Do the translation inside `api.js`** (an adapter), using the mapping in Section 17.3, so UI code keeps its current data shapes.
3. **Keep the mock implementation available** behind a switch (for example `VITE_USE_MOCK_API`) until the backend is stable. This matches the earlier instruction that mock functionality stays until the FastAPI backend exists. (A recommendation; no code is changed by this task.)
4. Swap one endpoint group at a time, starting with the ones that need no auth change.

### 24.2 Required frontend changes

| ID | Change | Where (today) | Needed for | Finding |
| --- | --- | --- | --- | --- |
| **FC-1** | Pass the CV id when starting an interview — e.g. `startInterview(config, cvId)` using `cvFile.id` | `InterviewSetup.jsx` → `InterviewContext.start` → `api.startInterview` | E11 | F1 |
| **FC-2** | Keep `question.id` in the session and call `submitAnswer(sessionId, question.id, answer)` instead of passing the array index | `InterviewContext.jsx` | E15, E16 | F2 |
| **FC-3** | Call `deleteCV` from "Remove"/"Replace"; on app start call `listCVs` to restore the CV | `useCVUpload.js`, `AppContext.jsx` | E08, E10 | F9 |
| **FC-4** | Authentication: sign-in/registration screens, token handling (memory), `Authorization` header, one silent refresh on `TOKEN_EXPIRED`, sign-out calling E04, hydrate `user` from `GET /users/me` | `Landing.jsx`, `Navbar.jsx`, `AppContext.jsx`, new pages | E01–E05 | F10 |
| **FC-5** | Format `completed_at` into the existing display string in the adapter | `api.js` | E18, E19 | F5 |
| **FC-6** | Throw a typed `ApiError { status, code, message, retryable }`; show `message`; client-side timeout; handle 401/429 | `api.js`, screens' catch blocks | all | F13 |
| **FC-7** | Empty states: guard `rankSkills` and render Dashboard/Performance for users with no completed interviews | `utils/scoring.js`, `Dashboard.jsx`, `Performance.jsx` | E19–E21 | F26 |
| **FC-8** | Use `XMLHttpRequest` (or equivalent) so `onProgress` reports real upload progress | `api.js` | E07 | F14 |
| FC-9 | Call `abandonInterview(id)` when the user confirms "Exit" | `InterviewProgress.jsx` | E13 | F12 |
| FC-10 | Remove or replace "Reset demo data" in production builds | `Profile.jsx` | OD-9 | F11 |
| FC-11 | Optionally read dashboard stats and the trend from E21 instead of computing from the full history | `Dashboard.jsx`, `Performance.jsx` | E21 | F6 |
| FC-12 | Read the API base URL from `import.meta.env.VITE_API_BASE_URL` | `api.js` | all | — |

FC-1 to FC-8 are required for the first working version; FC-9 to FC-11 belong to the second iteration; FC-12 is trivial and needed throughout.

### 24.3 Target behaviour of each `api.js` function

| Function | New behaviour |
| --- | --- |
| `uploadCV(file, onProgress)` | multipart `POST /cvs` with progress events → `{ id, name }` |
| `startInterview(config, cvId)` | `POST /interviews`; map enums; return `{ id, questions:[{id, text, type}], config }` |
| `submitAnswer(sessionId, questionId, answer)` | `PUT …/answer` → `{ ok: true }` |
| `getEvaluation(sessionId, question)` | `POST …/evaluation` → UI `ev` shape |
| `completeInterview({ session })` | `POST …/complete` → UI results shape (client `items` no longer sent) |
| `getInterviewResults(meta)` | `GET /interviews/{meta.id}/results` → UI results shape |
| `getInterviewHistory()` | `GET /interviews?status=completed&limit=100` → array of UI `meta` |
| `getSkills()` | `GET /performance/skills` → object preserving order |
| `updateProfile(profile)` | `PATCH /users/me` → `{ id, name, email }` |
| *new:* `getMe`, `deleteCV`, `listCVs`, `abandonInterview`, `register`, `login`, `logout`, `getSummary` | thin wrappers around E05, E10, E08, E13, E01, E02, E04, E21 |

### 24.4 Suggested implementation order

| Phase | Work | Primary owner (from the proposal) |
| --- | --- | --- |
| 0 | Review this document; settle OD-1, OD-2, OD-3, OD-5, OD-8 | whole team |
| 1 | FastAPI skeleton, configuration, `/health`, error envelope, request IDs; database schema and migrations | Backend, Database |
| 2 | Users and authentication (per OD-1); `GET/PATCH /users/me` | Backend |
| 3 | CV upload, parsing, S3 storage, delete | Backend, ML |
| 4 | Interview creation with questions and ideal answers (first question source) | Backend, GenAI, ML |
| 5 | Answer storage and evaluation (similarity + interim scoring + rule-based feedback) | ML, Backend |
| 6 | Completion, results, history, performance | Backend, Database |
| 7 | Frontend adapter swap per group (FC-1 to FC-8), keeping the mock switch | Frontend |
| 8 | AWS deployment, CloudWatch dashboards/alarms, security checklist (Section 19) | Cloud/DevOps |
| 9 | Second-iteration endpoints and calibration of scoring against human ratings | all |

### 24.5 Contract verification

- Generate the OpenAPI document from FastAPI and diff it against Sections 4–14.
- Use the JSON examples in this document as test fixtures (the adapter tests should turn each API example into the UI shape shown in Section 17.3).
- Keep one end-to-end test per Flow A–E (Section 3.3).

---

## Appendix A — Validation report

This appendix records the checks required before the specification could be called complete. "Verified mechanically" means a script compared this document with the source code or with itself; everything else was checked by reading.

### A.1 Every frontend service function against the API

| Function | Endpoint | What the UI sends today → what the API needs | What the UI consumes | Result |
| --- | --- | --- | --- | --- |
| `uploadCV(file, onProgress)` | E07 | file → file | `res.id` only | Supported. Real progress needs XHR (FC-8); auth header (FC-4) |
| `startInterview(config)` | E11 | `{role,type,diff,n}` → **plus `cv_id`** | `id`, `questions[].text/type` (**plus `id`**) | Supported **after FC-1, FC-2** |
| `submitAnswer(sessionId, index, answer)` | E15 | index → **question id** | nothing | Supported **after FC-2** |
| `getEvaluation(sessionId, question, answer)` | E16 | question text + answer → **question id only** | `score, cats, strengths, weaknesses, tip, ideal` | Supported **after FC-2**; all six fields present in the response |
| `completeInterview({session, config, items})` | E14 | client `items` → **nothing** (server aggregates) | `meta, items[{q,ev}], extraStrength, extraImprovement, recommendations` | Supported; the client payload becomes unnecessary (F4) |
| `getInterviewResults(meta)` | E18 | `meta` → `meta.id` | same results shape | Supported via adapter |
| `getInterviewHistory()` | E19 | — | `id, date, role, type, diff, n, score, status` | Supported via adapter; ISO date formatting (FC-5); 100-row cap (F6) |
| `getSkills()` | E20 | — | ordered skills object | Supported via adapter (F7); **empty state breaks the UI (FC-7)** |
| `updateProfile(profile)` | E06 | `{name,email}` → `{name?,email?}` | returned user | Supported |

Verified mechanically: all nine function names found in `api.js` appear in the Section 3.1 table; every field name above exists in the contract.

### A.2 Frontend operations → endpoint

| Frontend operation | Endpoint(s) | Note |
| --- | --- | --- |
| Upload / replace CV | E07 (+ E10 for replace) | |
| Remove CV | E10 | no function today (F9) |
| Restore CV after refresh | E08 / E09 | no function today (F9) |
| Choose role / type / difficulty / count; type or clear an answer; next question; theme toggle; history filter; estimated time | none — client-only | filter may use E19's optional `type` |
| Start interview | E11 | |
| Submit answer | E15 | |
| View evaluation, expand "stronger answer example" | E16 (the example is in the same response) | no extra call |
| Finish interview | E14 | |
| Exit interview | E13 | no function today (F12) |
| Open results (dashboard, history) | E18 | |
| Open per-question feedback modal | none — data is already inside the results payload | |
| Dashboard figures | E19 + E20 today; E21 recommended | |
| Performance page | E19 + E20 today; E21 recommended | |
| Save profile | E06 | |
| Load current user | E05 | no function today (F10) |
| Sign in / register / sign out | E02 / E01 / E04 (+ E03) | no UI today (F10) |
| Reset demo data | none | OD-9 |

### A.3 Do the database models support every operation?

| Operation | Reads | Writes |
| --- | --- | --- |
| Upload CV | — | `cvs`, `cv_profiles`, `cv_skills`, S3 |
| Delete CV | `cvs` | `cvs`, `cv_profiles`, `cv_skills`, `interviews.cv_id` → NULL, S3 |
| Create interview | `cvs`, `cv_profiles`, `cv_skills`, (`question_bank`) | `interviews`, `interview_questions` |
| Submit answer | `interviews`, `interview_questions` | `answers` |
| Evaluate | `answers`, `interview_questions` (ideal answer) | `evaluations` |
| Complete | `evaluations`, `answers`, `interview_questions` | `interview_results`, `interviews`, `user_performance` |
| Results | `interview_results`, `interviews`, `interview_questions`, `answers`, `evaluations` | — |
| History | `interviews` | — |
| Skills / summary | `user_performance`, `interviews` | — |
| Profile | `users` | `users` |
| Resume state (E12) | `interviews`, `interview_questions`, `answers`, `evaluations` | — |

Every field the UI displays is stored: `meta` fields in `interviews`; evaluation fields in `evaluations` (+ `ideal_answer` in `interview_questions`); results strings in `interview_results`; skills in `user_performance`.

### A.4 Alignment with the proposal

| Proposal statement | Where it is addressed | Status |
| --- | --- | --- |
| User uploads a CV (PDF/DOCX converted to text) | E07, step A | covered |
| User selects a target job role | E11 (`target_role`, free text) | covered |
| Answers via text | E15 | covered |
| FastAPI backend connecting frontend and AI modules | Sections 4, 16 | covered |
| Data stored in PostgreSQL/MySQL on AWS RDS | Section 15 | covered; engine open (OD-2) |
| Sentence Transformers / BERT / DistilBERT score answers against ideal responses | Section 16 steps E–F | covered; BERT/DistilBERT role and category methods open (OD-8) |
| Confidence score, strengths, weaknesses, improvement suggestions | E16, E14, E18 | covered; exact formula open (OD-8) |
| GenAI generates personalized questions and ideal answers | E11, steps C–D | covered; **optional** per proposal (OD-3) |
| GenAI generates personalized **follow-up** questions | Section 22 | **not supported by the current UI (F21)**; deferred |
| Whisper speech-to-text | Section 22 | in the ML role and value proposition only; deferred (OD-6) |
| Job descriptions as input data | Section 22 | no workflow step or UI field; deferred (OD-7) |
| Curated question banks and career resources "used for RAG" | `question_bank`, Section 16.3 | mechanism open (OD-5) |
| Web-scraped postings, synthetic Q&A data | — | offline data/training pipeline; **no runtime API**, outside this document |
| AWS EC2, S3, RDS, API Gateway, CloudWatch | Section 20 | covered; no other AWS service in the baseline |
| Results shown in React; history and performance stored | E18–E21 | covered |
| No orchestration framework specified | — | none assumed |

**Additions beyond the proposal**, all tagged **[Recommended]** so they can be rejected: authentication and a user model, error envelope and API conventions, `question_source` switch, interim scoring heuristics, rule-based feedback text, abandon/resume endpoints, the `user_performance` table. **No contradiction with the proposal was found.** One brief-versus-proposal nuance: the brief's example routes feedback wording through GenAI, whereas the proposal assigns GenAI only to questions and ideal answers; this document keeps GenAI optional for wording (step H).

### A.5 Frontend items that cannot be supported by the proposed backend as the UI stands today

| Item | Why | Resolution |
| --- | --- | --- |
| Starting an interview | UI never sends the CV id (F1) | FC-1 |
| Answer/evaluation calls | UI addresses questions by index/text (F2) | FC-2 |
| Authenticated access | no login, tokens or 401 handling (F10, F13) | FC-4, FC-6 (method: OD-1) |
| New users with no history | `rankSkills({})` throws (F26) — verified by running the function | FC-7 |
| Real upload progress | `fetch` has none (F14) | FC-8 |
| CV removal / restore | no API call, state in memory (F9) | FC-3 |
| Exit interview cleanup, resume | no API call (F12) | FC-9 (optional) |
| "Reset demo data" | no production meaning (F11) | OD-9, FC-10 |
| Dynamic follow-up questions | fixed question count (F21) | deferred |
| Speech answers | text-only UI (F22) | deferred (OD-6) |
| Job description | no field (F23) | deferred (OD-7) |
| Full-history assumptions | dashboard/trend computed from a complete list (F6) | E21 / FC-11, or the 100-row cap |

### A.6 Missing backend requirements identified

Neither source defines these; they were **not silently invented** — each is either an open decision or an explicit provisional value:

- Authentication method (OD-1), database engine (OD-2), GenAI provider (OD-3), CV structure extraction (OD-4), question source/RAG (OD-5), scoring formula (OD-8), retention and privacy (OD-10), frontend hosting (OD-11), gateway type (OD-12), latency and sizing (OD-13).
- Provisional values to confirm: maximum role length 100, name length 2–100, minimum CV text length (not set; configurable), token lifetimes, rate-limit numbers, mixed-interview ratio.
- Unstated assumption: **interviews are in English** (the UI copy is English; neither source mentions other languages).
- Not specified anywhere and not required for the MVP: cost budgets for GenAI calls, monitoring thresholds, backup/restore targets.

### A.7 Totals

| Item | Count |
| --- | --- |
| API endpoints | **22** (9 Core · 7 Supporting · 6 Recommended); 16 in the first working version if OD-1 selects login |
| Frontend service functions analysed | 9 (all mapped) |
| Frontend findings | 26 (F1–F26) |
| Required / optional frontend changes | 12 (FC-1…FC-12) |
| Database tables | 12 (10 core + `refresh_tokens` conditional on OD-1 + `question_bank` conditional on OD-5) |
| Error codes | 31 |
| Security requirements | 30 (S-01…S-30) |
| Open decisions | 13 (OD-1…OD-13) |
| JSON examples validated as syntactically valid | all in this document |

### A.8 How this was validated, and its limits

Verified mechanically (script run against the repository and this file): the nine `api.js` functions are all mapped; the endpoint catalog has 22 unique IDs, each with a detail section whose method and path match; classes total 9/7/6; every `F`, `FC`, `S`, `OD`, `E` reference resolves; every error code used in the text exists in the catalog; every in-document link resolves; all JSON examples parse; example numbers are consistent (history average = summary average, Communication = rounded mean of Clarity and Confidence, skills sorted, question counts match); the UI limits quoted (5 MB, PDF/DOCX, answer 30–1500, role ≥ 3) and findings F1, F4, F5, F7 and F26 match the actual source.

Not verified, because nothing exists yet to test against: that a real backend will meet latency targets; that chosen models will produce well-distributed scores; contract tests against a running API. AWS limits were checked against AWS documentation on the date above and should be rechecked at deployment. **Everything in this document is specification, not implementation.**
