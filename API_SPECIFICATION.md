# AI Interview Coach — API Specification

| | |
| --- | --- |
| **Document status** | Draft **v0.2** — design only. The team's working technical decisions are finalized (Section 1.6) |
| **Date** | October 19, 2026 |
| **Team** | Capstone Team 147 (DEPI) |
| **Sources of truth** | (1) `AI_Capstone_Project_Proposal_Team147.docx` for intended technical scope; (2) the React/Vite frontend (`ai-interview-coach` v0.1.0), in particular `src/services/api.js` and how the UI actually consumes it; (3) the **finalized working decisions D1–D8** (Section 1.6), adopted because the team is inactive and progress must not wait |
| **Implementation status** | **Nothing in this document is implemented.** There is no FastAPI code, no database, no downloaded model and no cloud resource; no Python package has been installed. The frontend still runs on its mock service layer. **The AI evaluation described here has not been built, tested or validated.** |

### What changed from v0.1

- Scope is now a **local-first MVP**: PostgreSQL on the developer's machine, no authentication yet (single-user demo), no paid or external AI service, no AWS.
- Questions come from a **curated question bank with reference answers**; feedback comes from **transparent rule-based templates**; answers are scored by a **local Sentence Transformers model plus explicit criteria**.
- The per-answer category **"Confidence" is replaced by "Structure"**, because the decisions forbid claiming to measure psychological confidence from text (Section 16, FC-13).
- New sections: **25** (project structure, dependencies, environment variables, local setup) and **26** (beginner-friendly implementation sequence). Section 20 (AWS) is now a conditional later phase; Section 23 separates resolved from still-open questions.
- New endpoint **E23** (demo-only reset) so the existing "Reset demo data" button keeps working; authentication endpoints E01–E04 are **deferred**.

**How to read this document.** Statements are tagged by origin so the team can tell what is decided from what is proposed:

- **[Proposal]** — stated in the capstone proposal.
- **[Decided]** — one of the eight finalized working decisions (D1–D8).
- **[Recommended]** — a design choice made in this document to fill a gap; reversible.
- **[Deferred]** — intentionally postponed; not part of the local MVP.
- **[Open]** — genuinely unresolved; see [Section 23](#23-open-decisions--questions).

---

## Table of contents

1. [System Overview](#1-system-overview) — incl. the [decision register](#16-finalized-working-decisions-d1d8)
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
20. [AWS Architecture (later phase)](#20-aws-architecture-later-phase)
21. [MVP Scope](#21-mvp-scope)
22. [Future Enhancements](#22-future-enhancements)
23. [Open Decisions / Questions](#23-open-decisions--questions)
24. [Frontend Integration Plan](#24-frontend-integration-plan)
25. [Local Development: Structure, Dependencies and Environment](#25-local-development-structure-dependencies-and-environment)
26. [Implementation Sequence (beginner-friendly)](#26-implementation-sequence-beginner-friendly)
- [Appendix A — Validation report](#appendix-a--validation-report)

---

## 1. System Overview

### 1.1 What the product is

AI Interview Coach helps job seekers and students prepare for interviews. A user uploads a CV, selects a target role, answers interview questions by text, and receives an AI-evaluated confidence score, strengths, weaknesses and improvement suggestions. With GenAI, the system can also produce personalized questions and ideal-answer suggestions **[Proposal §2]** — GenAI is **deferred** in the local MVP (D4); a curated question bank with reference answers takes its place.

### 1.2 Intended end-to-end workflow

**[Proposal §4]** describes four stages, which this specification maps to API calls. The right-hand column states what the **local MVP** does at each stage.

| # | Proposal stage | Realised by | In the local MVP |
| --- | --- | --- | --- |
| 1 | **Input** — user uploads CV, selects target role, answers questions via text in React | `POST /cvs`, `POST /interviews`, `PUT …/answer` | as proposed |
| 2 | **Processing / backend** — FastAPI receives requests; data stored in PostgreSQL/MySQL | all endpoints; Section 15 | FastAPI + **local PostgreSQL** **[Decided D1, D2]** |
| 3 | **AI execution** — Sentence Transformers / BERT / DistilBERT score answers; a GenAI layer generates personalized questions and ideal answers | `POST /interviews` (questions), `POST …/evaluation` (scoring); Section 16 | **local Sentence Transformers + rule-based criteria**; questions and reference answers from a **curated bank**; BERT/DistilBERT and GenAI **deferred** **[Decided D4, D5]** |
| 4 | **Output** — score, strengths, weaknesses, suggestions returned to React; CloudWatch monitors the system | `POST …/evaluation`, `GET …/results` | rule-based templates; structured local logs instead of CloudWatch **[Decided D4, D8]** |

### 1.3 Technology scope: proposal versus finalized MVP

| Layer | Proposal | Local MVP decision | Status |
| --- | --- | --- | --- |
| Frontend | React.js | keep the existing React/Vite app unchanged; adapt only inside `api.js` later | **[Decided D1]** |
| Backend | Python, FastAPI | FastAPI + Python | **[Decided D1]** |
| Database | PostgreSQL or MySQL on AWS RDS | **PostgreSQL, local**; portable so it can later move to RDS; SQLite only as a *documented temporary fallback* | **[Decided D2]** |
| Authentication | not mentioned | deferred; single-user demo; architecture ready for it | **[Decided D3]** |
| Answer evaluation | Sentence Transformers, BERT / DistilBERT | local Sentence Transformers (candidate `sentence-transformers/all-MiniLM-L6-v2`) combined with explicit rule-based criteria; BERT/DistilBERT deferred | **[Decided D5]** |
| GenAI | OpenAI API or Amazon Bedrock, "optional" | **not used**; curated question bank with reference answers; rule-based feedback templates; GenAI is a possible later integration | **[Decided D4]** |
| RAG | curated banks and resources "used for RAG" | bank retrieval and ranking only (no generation); RAG with generation deferred | **[Decided D4]**, details **[Open]** (OD-5) |
| Speech | Whisper | deferred; text answers only | **[Decided D6]** |
| CV parsing | CVs converted to text | free Python libraries; metadata and extracted data in PostgreSQL; file kept only in private local storage | **[Decided D7]** |
| Infrastructure | AWS EC2, S3, RDS, API Gateway, CloudWatch | later phase; availability in AWS Academy unconfirmed; nothing created | **[Decided D8]** |
| Orchestration framework | "None specified yet" | none | **[Proposal]** |

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

### 1.6 Finalized working decisions (D1–D8)

The team is inactive, so these eight decisions are the agreed working plan. They are **not** re-opened in this document; where they leave a gap, the gap is listed in Section 23.2.

| ID | Decision | Consequence in this specification | Where |
| --- | --- | --- | --- |
| **D1** | **Development approach.** Develop and test locally before any AWS deployment. Preserve the existing React/Vite frontend and its functionality. Build the backend with FastAPI and Python. Do not overwrite or recreate the frontend. | The backend is a new, separate folder. The frontend is changed only through the small, listed adapter changes (FC-1…FC-14), never rebuilt. | 24, 25, 26 |
| **D2** | **Database.** PostgreSQL locally as the primary development database; no paid database subscription; configuration portable to AWS RDS later. If local PostgreSQL proves a blocker, document SQLite as a *temporary* fallback — do not silently change the primary decision. | Portable SQLAlchemy types only; database URL from environment; SQLite fallback procedure and limits written down. | 15, 25 |
| **D3** | **Authentication.** Defer full authentication in the first local MVP. Support a single-user demonstration without exposing private data. Keep the architecture ready for authentication. Authentication must exist before any public deployment exposes private data. | `AUTH_MODE=demo` resolves one seeded demo user; E01–E04 are deferred; start-up guards stop demo mode from running outside local development. | 5, 19 |
| **D4** | **Generative AI.** No OpenAI, Bedrock or other paid API for the MVP. Curated question bank with reference answers. Rule-based, transparent feedback templates. GenAI remains an optional future integration. | `question_source` is always `bank`; `feedback_source` is always `rules`; no AI keys; no CV text leaves the machine. | 8, 16, 22 |
| **D5** | **Answer evaluation.** Local Sentence Transformers for semantic similarity if the machine supports it; `all-MiniLM-L6-v2` as initial candidate; combine similarity with explicit criteria; document that similarity is not a complete measure of answer quality; **do not claim to measure psychological confidence from text**; scoring lives only on the backend and frontend-submitted scores are never trusted. | Category **Confidence → Structure**; overall figure called *score*; documented limitations and an unvalidated-status notice; complete-interview ignores client scores. | 10, 11, 16, 17, FC-13 |
| **D6** | **Interview format.** Text only. Whisper deferred. Core workflow: CV upload, target role, interview creation, question presentation, answer submission, evaluation, feedback, results, history. | No audio endpoints in the MVP; `input_mode` is always `text`. | 21, 22 |
| **D7** | **CV processing.** Free Python libraries for PDF/DOCX text extraction; validate type and size; CV metadata and extracted information in PostgreSQL; uploaded files never in a publicly accessible location; document safe local storage and the migration path to private S3. | `StorageBackend` abstraction: private local directory now, private S3 later; magic-byte validation; extracted data in PostgreSQL. | 6, 15, 19, 25 |
| **D8** | **AWS.** AWS Academy is the available educational resource, but services and credits are unconfirmed. Do not assume unrestricted access; create no resources; incur no costs; deployment is a later phase. | Section 20 is conditional and non-committal; no requirement in the MVP depends on AWS. | 20 |

### 1.7 Proposal traceability: what is kept, reduced or deferred

| Proposal requirement | Status in the local MVP | Note |
| --- | --- | --- |
| CV upload (PDF/DOCX) converted to text | **Included** | D7 |
| Select a target job role | **Included** | free text or preset (E11) |
| Personalized interview questions from CV + role | **Included in reduced form** | questions are *selected and ranked* from a curated bank, with skill-based templates; they are not *generated* (D4). The landing-page wording must reflect this (FC-14) |
| Text answers | **Included** | D6 |
| FastAPI backend linking React and the AI modules | **Included** | D1 |
| Data stored in PostgreSQL / MySQL on AWS RDS | **Included locally** (PostgreSQL) | RDS later, if permitted (D2, D8) |
| Sentence Transformers semantic similarity against ideal responses | **Included** | local model (D5); unvalidated until tested |
| BERT / DistilBERT scoring | **Deferred** | not part of D5; the scoring interface stays replaceable |
| A "confidence score" | **Included in reduced form** | exposed as an overall *answer score*; psychological confidence is **not** measured (D5). This deliberately changes the proposal's wording |
| Strengths and weaknesses | **Included** | derived from explicit criteria and templates |
| Improvement suggestions | **Included** | template-based |
| GenAI personalized questions and ideal-answer suggestions | **Deferred** | reference answers come from the bank (D4) |
| GenAI personalized follow-up questions | **Deferred** | also unsupported by the current UI (F21) |
| Whisper speech-to-text | **Deferred** | D6 |
| Job descriptions as input data | **Not in the MVP; unresolved** | OD-7 |
| RAG over curated banks and career resources | **Reduced form** | retrieval/ranking of bank entries only; generation-based RAG deferred |
| Scraped job postings, synthetic Q&A data | **Unresolved** | offline data work; no runtime API; unclear whether the MVP needs it (OD-14) |
| Performance tracking and stored history | **Included** | E19–E21 |
| Validation: correlation of AI scores with human-rated benchmarks | **Retained as the acceptance test; not yet run** | plan in Section 16.9 |
| AWS EC2, S3, RDS, API Gateway, CloudWatch | **Deferred** | D8; local equivalents defined |

---

## 2. Current Frontend Analysis

Method: the full `src/` tree was inspected, and `api.js` call sites were located with a text search (results in 2.4). Findings that affect the backend are numbered **F1–F27** and referenced throughout.

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
| **F10** | No login, registration or token handling; the user is seeded from `DEMO_USER`; "Sign out" only navigates. | With the decided single-user demo mode (D3) **no UI change is required for the local MVP**: the backend resolves the demo user itself. Real authentication needs screens and token handling later (FC-4, Phase 2, before any public deployment). |
| **F11** | Email is editable in Profile; "Reset demo data" clears the CV and history. | In demo mode both work: profile edits update the single demo user, and "Reset demo data" maps to a development-only endpoint (E23). **Behaviour differs from the mock:** the mock restored four sample interviews, whereas a real reset leaves an empty history (see F26). |
| **F12** | "Exit interview" performs no API call; refreshing the page loses the session. | Optional `abandon` endpoint (E13) and `GET /interviews/{id}` (E12) to enable cleanup and future resume. |
| **F13** | Error handling is generic (fixed strings per screen); no use of error codes, no 401 handling, no request timeout, no retry. | Spec defines machine-readable error codes (Section 18); frontend should map them (FC-6). |
| **F14** | Upload progress is a callback `onProgress(0–100)`. Browser `fetch` does not expose upload progress. | Adapter must use `XMLHttpRequest` (or an HTTP library that wraps it). |
| **F15** | Question counts of 5/10/15 are offered; the mock reuses its small pool with a "Follow-up" suffix for extras. | Real generation must produce *n* distinct questions. |
| **F16** | "Confidence" is used for two things — the dashboard label "Average confidence" (the mean overall score) and a per-answer category — and the landing page promises to track "confidence". Decision D5 forbids claiming to measure psychological confidence from text answers. | The per-answer category becomes **`structure`** and the overall figure is called a *score*. UI labels and `buildBreakdown` must change (FC-13). |
| **F17** | The user's own answer text is never displayed back (Results shows question + feedback only). | Answer text is stored and may be returned, but the UI does not need it for MVP. |
| **F18** | Custom role has a minimum length (3) but no maximum. | Server enforces a maximum (100 characters). |
| **F19** | File type is validated by extension only. | Server must validate content (magic bytes), not just name. |
| **F20** | No pagination anywhere. | See F6. |
| **F21** | The number of questions is fixed at creation. The proposal's "personalized follow-up questions" would add questions dynamically. | Dynamic follow-ups are **not supported** by the current UI; deferred (Section 22). |
| **F22** | Answers are text only. | Matches D6; Whisper/speech input is deferred (OD-6 resolved). |
| **F23** | No field for a job description, although the proposal lists job descriptions among input data. | Not in the MVP; remains unresolved (OD-7). |
| **F24** | History `status` is always `"Completed"`. | History endpoint returns completed interviews only by default. |
| **F25** | Enum values are display strings (`"Intermediate"`). | API uses lowercase enums (`intermediate`); adapter maps both ways. |
| **F26** | **Empty state is unsupported.** `rankSkills({})` throws a `TypeError` (`sorted[0][0]` on an empty list), so the Dashboard and Performance page break for a user with no completed interviews. The mock always has data, so this never showed. | Real new users have no history; E20/E21 return empty values. Frontend must handle it (FC-7). |
| **F27** | Some UI wording over-claims relative to the decided MVP: "Questions generated from your own experience" (questions are selected from a bank), "AI recommendations" / "AI insight" (rule-based templates), "Average confidence". | Copy should describe what the system actually does — FC-14 (recommended) and FC-13 (required for "confidence"). |

---

## 3. Frontend → Backend Mapping

### 3.1 Every existing service function

Endpoint IDs (`E01`…`E22`) refer to the catalog in [Section 4.4](#44-endpoint-catalog) and the detailed sections that follow.

| Frontend feature | Service function | Method & endpoint | Request | Response (fields the UI uses) | Database | AI / ML | Possible errors |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Upload CV | `uploadCV(file, onProgress)` | `POST /api/v1/cvs` **E07** | `multipart/form-data`, field `file` (PDF/DOCX, ≤ 5 MB) | `cv.id` (UI also shows name/ext/size, which come from the local file today); plus `extracted.skills` for later personalization | insert `cvs`, `cv_profiles`, `cv_skills`; file saved to **private local storage** (S3 later) | text extraction with free Python libraries (deterministic); rule-based skill extraction (taxonomy, OD-15) | `UNSUPPORTED_FILE_TYPE`, `FILE_TOO_LARGE`, `CV_UNREADABLE`, `DATABASE_UNAVAILABLE`, `STORAGE_UNAVAILABLE` |
| Start interview (select questions) | `startInterview(config)` | `POST /api/v1/interviews` **E11** | JSON `{cv_id, target_role, interview_type, difficulty, question_count}` | `id`, `questions[{id, position, text, type}]`, echoed `config` | insert `interviews`, `interview_questions` (reference answer and key points copied from the bank, hidden) | none — **deterministic selection/ranking** from the curated `question_bank` (skill templates filled from the CV); optional local embeddings for ranking | `CV_REQUIRED`, `CV_NOT_FOUND`, `INVALID_INTERVIEW_CONFIG`, `QUESTION_BANK_INSUFFICIENT` |
| Submit answer | `submitAnswer(sessionId, questionIndex, answer)` | `PUT /api/v1/interviews/{id}/questions/{qid}/answer` **E15** | JSON `{answer_text}` | `{id, question_id, submitted_at}` (UI ignores the body) | upsert `answers` | none | `ANSWER_EMPTY`, `ANSWER_TOO_SHORT`, `ANSWER_TOO_LONG`, `INTERVIEW_NOT_FOUND`, `QUESTION_NOT_FOUND`, `INTERVIEW_NOT_ACTIVE`, `ANSWER_ALREADY_EVALUATED` |
| Evaluate answer | `getEvaluation(sessionId, question, answer)` | `POST /api/v1/interviews/{id}/questions/{qid}/evaluation` **E16** | no body (answer already stored) | `overall_score`, `category_scores`, `strengths`, `weaknesses`, `improvement_tip`, `ideal_answer` | insert `evaluations` (idempotent) | **local Sentence Transformers similarity + explicit rule-based criteria** (ML + deterministic); template feedback | `ANSWER_NOT_FOUND`, `AI_SERVICE_UNAVAILABLE` (local model not loaded), `INTERVIEW_NOT_ACTIVE` |
| Finish interview | `completeInterview({session, config, items})` | `POST /api/v1/interviews/{id}/complete` **E14** | no body (client `items` and scores are ignored, F4) | full results payload (same as E18) | insert `interview_results`; update `interviews`, `user_performance` | none — deterministic aggregation; rule-based recommendations | `INTERVIEW_INCOMPLETE`, `INTERVIEW_NOT_FOUND`, `INTERVIEW_NOT_ACTIVE`, `DATABASE_UNAVAILABLE` |
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
| Register / sign in / refresh / sign out | **E01–E04** (**deferred**, D3) | no auth UI (F10); not needed for the local demo, required before any public deployment |
| Abandon an interview on "Exit" | `POST /interviews/{id}/abandon` **E13** | Exit is navigation only (F12) |
| Resume / reload an interview | `GET /interviews/{id}` **E12**, `GET …/evaluation` **E17** | session lost on refresh (F12) |
| Dashboard stats without loading all history | `GET /performance/summary` **E21** | stats computed client-side (F6) |
| Liveness / readiness checks | `GET /health` **E22** | operational need, not UI |
| "Reset demo data" | `POST /demo/reset` **E23** (development-only) | maps the existing button onto a demo-mode endpoint (F11) |

### 3.3 End-to-end contract flows

Each flow shows the exact hand-off: **React → HTTP → FastAPI → processing → HTTP → React**. In the local MVP the browser talks directly to FastAPI on `http://127.0.0.1:8000` (no gateway) and no `Authorization` header is needed (demo mode, D3). Full field tables are in the endpoint sections.

#### Flow A — CV upload (`multipart/form-data`)

```
React (useCVUpload → api.uploadCV)
  │  validates ext ∈ {pdf, docx}, size ≤ 5 MB            (UX only; server re-validates)
  │  POST /api/v1/cvs
  │  Content-Type: multipart/form-data; boundary=…
  │  part "file": binary, filename="cv.pdf", Content-Type: application/pdf
  ▼
FastAPI
  │  1. resolve current user (demo user)      4. extract text (free Python libraries)
  │  2. enforce size limit while reading      5. rule-based skill extraction
  │  3. verify magic bytes + extension        6. save file in PRIVATE local storage (random name);
  │                                              insert cvs / cv_profiles / cv_skills in PostgreSQL
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
  │  validate body → load CV (cv_id is required, F1)
  │  select N questions from question_bank (role, type, difficulty; skill templates filled from the CV)
  │  copy each question's reference answer + key points into interview_questions (hidden)
  │  insert interviews + interview_questions in one transaction
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
  │       FastAPI: validate length 30–1500 (after trim) → upsert answers → 200/201 { id, … }
  │  2) POST /api/v1/interviews/{iid}/questions/{qid}/evaluation (no body)
  │       FastAPI: load answer + stored reference answer + key points
  │                → local embedding model: similarity to the reference (long answers are chunked)
  │                → explicit criteria (key-point coverage, structure cues, clarity cues)
  │                → category scores + overall score  (computed ONLY here, never taken from React)
  │                → strengths / weaknesses / tip from rule-based templates
  │                → insert evaluations → 201 { evaluation }
  ▼
React: adapter → { score, cats, strengths, weaknesses, tip, ideal } ; navigate /interview/evaluation
Retry rule: if step 2 fails, React keeps the typed answer and retries; both calls are idempotent.
```

#### Flow D — Finish and show results

```
React (Evaluation "Finish & view results" → InterviewContext.finish → api.completeInterview)
  │  POST /api/v1/interviews/{iid}/complete   (no body — the old client payload is ignored)
  ▼
FastAPI
  │  verify every question has an evaluation (else 409 INTERVIEW_INCOMPLETE)
  │  overall = round-half-up(mean(answer scores)); breakdown per category
  │  recommendations + two highlight strings chosen by rules from the weakest/strongest categories
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
  └─ GET /api/v1/performance/skills                       → ordered skills (EMPTY for a new user — F26)
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
| Authentication | **MVP:** none on the wire — the backend resolves one seeded demo user (`AUTH_MODE=demo`, D3). **Later:** `Authorization: Bearer <access_token>` on every endpoint except register, login, refresh and health (Section 5) |
| Idempotency | achieved naturally: `PUT answer` is an upsert, `POST evaluation` / `POST complete` return the stored result if repeated |
| Pagination | `limit` (default 50, max 100) and `offset` on list endpoints |
| Unknown / foreign resources | return `404` (not `403`) so IDs cannot be probed |
| Local base URL | `http://127.0.0.1:8000/api/v1` (FastAPI) with the Vite dev server on `http://localhost:5173` |
| Docs | FastAPI's generated OpenAPI document (served locally at `/docs`) should be kept in sync with this specification |

**Why no `success` wrapper.** The example envelope in the brief is reasonable but redundant here: the frontend already branches on HTTP status and only needs a stable error code and message. Keeping success bodies unwrapped matches FastAPI's natural output and lets adapter code stay small.

### 4.2 Logical layers (design only)

```
                        ┌────────────────────────────────────────────┐
React (Vite SPA)  ───►  │ API layer     routers, current-user         │
 api.js adapter         │               dependency, validation        │
                        ├────────────────────────────────────────────┤
                        │ Service layer deterministic business rules  │
                        │   interview lifecycle · question selection ·│
                        │   scoring rules · aggregation · ownership   │
                        ├───────────────┬──────────────┬─────────────┤
                        │ Similarity    │ CV parsing   │ Storage      │
                        │ engine        │ (pypdf,      │ backend      │
                        │ (local model  │  python-docx)│ local private│
                        │  or lexical)  │              │ → S3 later   │
                        ├───────────────┴──────────────┴─────────────┤
                        │ Repository layer  (PostgreSQL via SQLAlchemy)│
                        └────────────────────────────────────────────┘
                          (a GenAI adapter is NOT part of the MVP — Section 22)
```

The similarity engine, the storage backend and the current-user dependency sit behind small interfaces so that the later changes — S3 storage, real authentication, a different scoring model or an optional GenAI adapter — replace one component instead of rewriting endpoints.

### 4.3 Request lifecycle

1. The browser sends the request to FastAPI (locally, directly; in a later AWS phase through API Gateway).
2. FastAPI assigns a `request_id`, resolves the current user through one dependency (the demo user today, a token-derived user later), validates input, and checks ownership of every referenced resource.
3. The service layer runs deterministic logic; the similarity engine is called only for answer evaluation (Section 16).
4. Database writes for one operation happen in one transaction.
5. The response (or the error envelope) is returned with `X-Request-ID`; structured logs go to the console/log file locally.

### 4.4 Endpoint catalog

**Priority classes**

- **Core** — maps directly to one of the nine existing `api.js` functions. Required for the current UI to work.
- **Supporting** — needed by the local MVP, but the current UI has no function for it (current user, delete CV, health, demo reset); needs a small frontend change or is operational.
- **Deferred** — authentication endpoints (D3). Not part of the local MVP; **required before any public deployment**.
- **Recommended** — improves robustness (refresh recovery, cleanup, aggregation); a second iteration of the local MVP.

| ID | Method | Path | Group | Purpose | Class |
| --- | --- | --- | --- | --- | --- |
| E01 | POST | `/auth/register` | Auth | Create account | Deferred (D3) |
| E02 | POST | `/auth/login` | Auth | Obtain tokens | Deferred (D3) |
| E03 | POST | `/auth/refresh` | Auth | Renew access token | Deferred (D3) |
| E04 | POST | `/auth/logout` | Auth | Revoke refresh token | Deferred (D3) |
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
| E23 | POST | `/demo/reset` | Operations | Delete all demo-user data (development only) — the "Reset demo data" button | Supporting |

**Totals: 23 endpoints = 9 Core + 4 Supporting (E05, E10, E22, E23) + 4 Deferred authentication (E01–E04) + 6 Recommended.** The **first local MVP is 13 endpoints** (9 Core + 4 Supporting); the 6 Recommended endpoints are the second iteration; authentication is Phase 2. All paths are relative to `/api/v1`. The Questions group (Section 8) has no standalone endpoint: questions are created by E11 and read through E11/E12.

### 4.5 Operational endpoints

### E22 — `GET /api/v1/health`

- **Purpose:** liveness/readiness probe for local checks (and, later, deployment monitors). Not used by the frontend.
- **Auth:** none. Exposes no secrets, hostnames, file paths or user data.
- **Response `200 OK`** when the service can serve traffic:

| Field | Type | Notes |
| --- | --- | --- |
| `status` | `"ok"` | |
| `version` | string | application version |
| `checks.database` | `"ok"` | `SELECT 1` succeeded |
| `checks.models` | `"ok"` | the similarity model finished loading (Section 16.6), or `"lexical"` when `SIMILARITY_BACKEND=lexical` was chosen deliberately |
| `checks.storage` | `"ok"` | the private CV directory exists and is writable |
| `checks.question_bank` | `"ok"` | the bank contains questions (a count, not content, may be logged) |

```json
{ "status": "ok", "version": "0.1.0",
  "checks": { "database": "ok", "models": "ok", "storage": "ok", "question_bank": "ok" } }
```

- **Not ready: `503 Service Unavailable`** with the same shape, `"status": "unavailable"` and each failing check set to `"unavailable"`. This probe is the one deliberate exception to the error envelope, because monitors read the body directly.
- **Database:** a trivial connectivity query. **AI/ML:** reports whether the model is loaded; runs no inference.

### E23 — `POST /api/v1/demo/reset`  (frontend: "Reset demo data")

- **Purpose:** delete everything the single demo user has created so the app returns to a clean state. It exists so the **existing "Reset demo data" button keeps working** (F11).
- **Availability:** registered **only** when `AUTH_MODE=demo` **and** `APP_ENV=development`. In any other configuration the route does not exist and returns `404 NOT_FOUND`, so it can never wipe real users' data.
- **Auth:** none (demo mode). **Request:** no body.
- **Response `200 OK`:** `{ "reset": true, "deleted": { "cvs": 1, "interviews": 4 } }`

```json
{ "reset": true, "deleted": { "cvs": 1, "interviews": 4 } }
```

- **Effects:** removes the demo user's `cvs` (and their stored files), `interviews` and everything below them (`interview_questions`, `answers`, `evaluations`, `interview_results`) and `user_performance`. The `users` row for the demo user and the shared `question_bank` are kept. **It does not re-create the four sample interviews the mock used to restore**, so the UI shows its empty state afterwards (F26).
- **Errors:** `NOT_FOUND` (404 when disabled), `STORAGE_UNAVAILABLE`, `DATABASE_UNAVAILABLE` (503).
- **Database:** deletes in one transaction; files are removed after the transaction commits.

---

## 5. Authentication

### 5.1 Decision **[Decided D3]**

Full authentication is **deferred** for the first local MVP. The backend supports a **single-user demonstration** and must not expose private data while doing so. The architecture is kept ready for authentication, and **authentication must be implemented before any public deployment exposes private data.**

Is deferral allowed by the project's requirements? The proposal never mentions authentication, so deferring does not conflict with it. The DEPI programme's own submission requirements were not available when this document was written and could not be checked — recorded as OD-16.

### 5.2 Demo mode (`AUTH_MODE=demo`)

| Aspect | Behaviour |
| --- | --- |
| Current user | one **seeded demo user** (name `Alex Morgan`, email `alex.morgan@email.com` — the same values as the frontend's `DEMO_USER`), created by the first database migration/seed step |
| Resolution | every protected route obtains its user from **one dependency**, `get_current_user`. In demo mode it returns the demo user; in a later mode it will read a token. Endpoints never read identity any other way |
| `Authorization` header | ignored if present (never an error) |
| E01–E04 | **not registered** in demo mode (they return `404 NOT_FOUND`) |
| E05, E06 | work on the demo user (so the Profile page works unchanged) |
| E23 | available (development only) |
| Frontend | **no change required** for the local MVP: "Sign in as Alex" simply navigates, as it does today (F10) |

**Safeguards so demo mode cannot leak private data (S-31, S-32):**

1. Bind the server to the loopback address only (`127.0.0.1`), never `0.0.0.0`.
2. **Refuse to start** if `AUTH_MODE=demo` and either `APP_ENV` is not `development` or the configured host is not a loopback address. This turns "authentication must exist before a public deployment" from a promise into a start-up check.
3. CORS allows only the local frontend origins; the `Host` header is checked against an allow-list.
4. Do not expose the dev server through a public tunnel while in demo mode.
5. Queries are **always filtered by `user_id`** even though only one user exists, so turning authentication on later changes the dependency, not the queries.

### 5.3 What "ready for authentication" means (design requirements)

- `users.password_hash` is nullable; `refresh_tokens` is specified but not created yet.
- Every table that holds user data carries `user_id` (directly or through its parent) and repositories take `user_id` as a parameter.
- Foreign or unknown ids already return `404` (S-02), so no code relies on "there is only one user".
- Error codes for authentication already exist in the catalog (`UNAUTHORIZED`, `TOKEN_EXPIRED`, …).
- Switching on authentication = set `AUTH_MODE=jwt`, supply `JWT_SECRET`, register E01–E04, unregister E23, implement FC-4 in the frontend. No endpoint contract in Sections 6–14 changes.

### 5.4 Phase 2 specification (deferred; required before public deployment)

The designs below are the **target** for Phase 2. They are **not** part of the local MVP and nothing here is decided beyond "email + password with short-lived access tokens". Still open for Phase 2: whether the refresh token travels in a cookie or the response body, and whether changing email needs verification (OD-1 residual). A managed identity provider (for example Cognito) was considered in v0.1 and is **not** assumed, because AWS availability is unconfirmed (D8).

| Item | Target value |
| --- | --- |
| Access token | signed JWT, short-lived (**[Recommended]** 15 minutes), sent as `Authorization: Bearer …`, kept in memory by the SPA |
| Refresh token | opaque random value, rotated on each use, stored **hashed** server-side; delivery cookie vs body **[Open]** |
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
- **Auth:** current user — the seeded demo user in the MVP, a Bearer token once authentication is enabled (Section 5).
- **Content-Type:** `multipart/form-data`

| Part | Type | Required | Rules |
| --- | --- | --- | --- |
| `file` | binary | yes | extension `pdf` or `docx`; **≤ 5 MB (5 × 1024 × 1024 bytes — the frontend rejects anything larger)**; content must match the extension (magic bytes); not encrypted/password-protected; must yield extractable text |

No other parts are accepted.

- **Example request**

```
POST /api/v1/cvs HTTP/1.1
Authorization: Bearer <token>        (not sent in demo mode)
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
| `extracted.experience` / `.education` / `.projects` | string[] | **provisional** best-effort text lines found by simple rules; may be empty; shape depends on OD-15 |

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
- **Database:** insert `cvs` (with the relative `storage_key`), `cv_profiles`, `cv_skills` in PostgreSQL in one transaction; if the transaction fails the stored file is removed.
- **Storage (D7):** the original file is written to the **private CV directory** under a random name (Section 25.5), never inside the frontend, a static-files mount or any web-served path, and its path is never returned. Moving to private S3 later only changes the storage backend.
- **Processing:** text extraction with free Python libraries (`pypdf` for PDF, `python-docx` for DOCX — Section 25.2); skills found by a **rule-based match against a curated skills list** (OD-15). No model download and no external service is involved in upload, so CV text never leaves the machine.
- **Notes:** the UI shows "Uploading & analyzing…" while this request runs, so parsing is **synchronous**. Progress percentages come from the browser's upload events, not from the server (F14). A user may hold several CVs; the UI uses the newest.

### E08 — `GET /api/v1/cvs`

- **Purpose:** list the user's CVs, newest first — lets the UI restore the CV after a refresh (F9). **Auth:** current user (Section 5).
- **Query:** `limit` (int, default 50, max 100), `offset` (int, default 0).
- **Response `200 OK`:** `{ "items": [ CV ], "total": integer, "limit": integer, "offset": integer }` where `CV` is the `cv` object from E07.
- **Status codes:** 200 · 401 · 503. **Database:** read `cvs` where `deleted_at IS NULL`.

### E09 — `GET /api/v1/cvs/{cv_id}`

- **Purpose:** one CV with its extracted data. **Auth:** current user (Section 5).
- **Response `200 OK`:** same body as the E07 response.
- **Errors:** `CV_NOT_FOUND` (404). **Database:** read `cvs`, `cv_profiles`, `cv_skills`.

### E10 — `DELETE /api/v1/cvs/{cv_id}`

- **Purpose:** remove a CV and its stored data (backs the UI's "Remove" button, which today only clears local state). **Auth:** current user (Section 5).
- **Response `204 No Content`.**
- **Effects:** deletes the stored file, `extracted_text`, `cv_profiles`, `cv_skills`. Interviews that used this CV are **kept**; their `cv_id` becomes `NULL` so history and results remain valid.
- **Errors:** `CV_NOT_FOUND` (404; also returned on a repeated delete). **Database:** delete/anonymise as above in one transaction.

---

## 7. Interview API

An *interview* is one practice session: a CV, a target role, a type, a difficulty, and *n* questions generated up front. Lifecycle: `in_progress → completed` or `in_progress → abandoned`.

### E11 — `POST /api/v1/interviews`  (frontend: `startInterview`)

- **Purpose:** create an interview and **select all of its questions** from the curated question bank in one call (the UI needs `questions` immediately to render "Question 1 of n" and the progress bar).
- **Auth:** current user — the seeded demo user in the MVP, a Bearer token once authentication is enabled (Section 5).
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

- **Status codes:** 201 · 401 · 404 · 422 · 503
- **Errors:** `CV_REQUIRED` (422 — `cv_id` absent/null; the UI shows "upload your CV first"), `CV_NOT_FOUND` (404), `INVALID_INTERVIEW_CONFIG` (422, with per-field `details`), `QUESTION_BANK_INSUFFICIENT` (422 — the bank cannot supply `question_count` questions for this combination; the message suggests fewer questions or another type), `DATABASE_UNAVAILABLE` (503)
- **Database:** insert `interviews`, then *n* rows in `interview_questions` (each carries a **snapshot** of the bank entry's hidden reference answer and key points), written in one transaction **only after selection succeeds**, so a failed call leaves nothing behind and the client can safely retry.
- **AI/ML:** none required. Selection is deterministic backend logic over the curated bank (rules below); local embeddings may optionally rank candidates (Section 16.3). No GenAI is used (D4). The call is fast enough to stay synchronous; the UI's "Generating questions…" spinner remains valid.

**Selection rules (MVP) [Recommended]** — thresholds and exact weights are tuned by the team and not claimed to be validated:

1. **Pool by type.** `technical` and `behavioral` draw only that type; `mixed` draws both in a configurable ratio (default about 60 % / 40 %).
2. **Role matching.** A preset role maps directly to bank `role_tags`. A custom role (free text, F18) is matched to the closest tags by keyword overlap — or, if the embedding model is loaded, by embedding similarity above a configurable threshold. With no match, only role-agnostic ("general") entries are used.
3. **Difficulty.** Exact difficulty first, then the adjacent level, then any level, until `question_count` is reached.
4. **CV awareness.** Bank entries of kind `skill_template` (for example "Your CV mentions {skill}. How have you used it in a project?") are instantiated with a skill found in the candidate's CV; entries whose `skill_tags` overlap the CV skills rank higher. At most one instantiation per skill.
5. **Uniqueness and order.** No repeated question text; the order is stable for a given interview (seeded by the interview id).
6. **No partial interviews.** If fewer than `question_count` questions qualify, fail with `QUESTION_BANK_INSUFFICIENT` rather than padding the list.

This is "CV-aware" only in the sense of tailoring selection and templates; it does not *generate* new questions (see FC-14 for the wording consequence).

### E12 — `GET /api/v1/interviews/{interview_id}`

- **Purpose:** current state of one interview, so the UI can recover after a refresh (F12). **Auth:** current user (Section 5).
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

- **Purpose:** mark an interview as abandoned when the user confirms "Exit". **Auth:** current user (Section 5).
- **Request:** no body. **Response `200 OK`:** `{ "id": uuid, "status": "abandoned" }`. Repeating the call returns the same `200`.
- **Errors:** `INTERVIEW_NOT_FOUND` (404), `INTERVIEW_NOT_ACTIVE` (409 — already completed).
- **Database:** update `interviews.status`. Abandoned interviews are excluded from history, results and performance.

### E14 — `POST /api/v1/interviews/{interview_id}/complete`  (frontend: `completeInterview`)

- **Purpose:** finish the interview, aggregate all stored evaluations, persist the results and update the user's performance.
- **Auth:** current user (Section 5). **Request:** no body. The frontend currently sends `{session, config, items}`; those values are **ignored** (F4).
- **Preconditions:** every question has an evaluation.
- **Response `200 OK`:** the full **results payload**, identical to E18 (see Section 11 for fields and example). If the interview is already completed, the stored payload is returned unchanged (idempotent).
- **Status codes:** 200 · 401 · 404 · 409 · 503
- **Errors:** `INTERVIEW_INCOMPLETE` (409; `details` lists unevaluated positions), `INTERVIEW_NOT_FOUND` (404), `INTERVIEW_NOT_ACTIVE` (409 — abandoned), `DATABASE_UNAVAILABLE` (503).
- **Database (single transaction):** insert `interview_results`; set `interviews.status = completed`, `completed_at`, `overall_score`; upsert `user_performance` rows.
- **AI/ML:** none — deterministic aggregation; recommendation text chosen by rules from the weakest and strongest categories (Section 16.4).

---

## 8. Question API

Questions have no endpoint of their own. They are **created** by E11 and **read** through E11 (on creation) and E12 (session recovery). This section defines the resource and its rules.

### 8.1 Question resource

| Field | Type | Visible to client | Notes |
| --- | --- | --- | --- |
| `id` | uuid | yes | stable for the life of the interview (F2) |
| `interview_id` | uuid | implied by path | |
| `position` | integer | yes | 1-based, unique within the interview. The frontend's `index` equals `position − 1` |
| `text` | string | yes | a bank question, or a skill template with the CV skill filled in |
| `type` | `technical` \| `behavioral` | yes | drives the "Technical Question" / "Behavioral Question" chip |
| `ideal_answer` | string | **no — only after the question has an evaluation** (returned inside the evaluation as `ideal_answer`) | snapshot of the bank's curated **reference answer**; the reference for scoring (Section 16) |
| `key_points` | string[] | **no** | snapshot of the bank's expected key points; used by the scoring criteria, never sent to the client |
| `source` | `bank` | no | always `bank` in the MVP; `genai` is reserved for a possible later integration |

### 8.2 Rules

1. **Count.** Exactly `question_count` questions, with distinct texts inside one interview (F15). If the bank cannot supply them, the call fails with `QUESTION_BANK_INSUFFICIENT` — it never returns fewer.
2. **Type mix.** `technical` → all technical; `behavioral` → all behavioral; `mixed` → a blend (**[Recommended]** configurable default of roughly 60 % technical / 40 % behavioral).
3. **Role, difficulty and CV skills** influence *selection and template filling* (E11 selection rules). They do not generate new questions.
4. **Reference answers and key points are secret until evaluated.** Revealing them before the user answers would defeat the exercise and leak the scoring reference. They never appear in E11 or E12.
5. **Immutable.** Questions are not edited after creation, and editing the bank later does not change existing interviews because each question stores a snapshot. Dynamic follow-up questions are a future capability (F21, Section 22).

### 8.3 Question-bank content requirements (derived from the UI)

The bank is **reference data owned by the team** (a table, Section 15, seeded from a file such as `question_bank.json`). Its size is dictated by what the frontend offers:

| Constraint | Why |
| --- | --- |
| The UI offers 5, 10 or 15 questions per interview | a (type, difficulty) combination needs **at least 15** eligible entries to serve `question_count = 15` without relaxing difficulty or failing |
| Three types (technical, behavioral, mixed) × three difficulties | 6 (type × difficulty) cells for single-type interviews; `mixed` draws from two of them |
| Seven preset roles plus free-text roles | role-specific entries for each preset role, plus a **general** (role-agnostic) set as the fallback for custom roles |
| Reference answers are scored with a model that **truncates at 256 word pieces** (Section 16.6) | write each reference answer to fit well under that limit (**[Recommended]** at most about 150 words) and give each entry 3–6 short `key_points` |

Who writes the content, how large the bank must be, and its licensing are **unresolved** (OD-14); until it exists E11 cannot work, which makes the bank the first blocking content task (Section 26).

---

## 9. Answer API

### E15 — `PUT /api/v1/interviews/{interview_id}/questions/{question_id}/answer`  (frontend: `submitAnswer`)

- **Purpose:** store (or replace) the candidate's text answer for one question. `PUT` makes retries safe: the UI keeps the typed text after a failure and may resubmit.
- **Auth:** current user — the seeded demo user in the MVP, a Bearer token once authentication is enabled (Section 5).
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
| `input_mode` | `"text"` | `"speech"` reserved for the future (Whisper is deferred, D6) |
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
- **Auth:** current user — the seeded demo user in the MVP, a Bearer token once authentication is enabled (Section 5). **Request:** no body (the answer was stored by E15; the frontend's extra `question`/`answer` arguments are not needed).
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
| `category_scores.structure` | integer 0–100 | "Structure" — replaces the former "Confidence" (D5, FC-13) |
| `strengths` | string[] | **1–3** items (the UI renders every item; an empty array would show an empty card) |
| `weaknesses` | string[] | **1–3** items |
| `improvement_tip` | string | one suggestion (`ev.tip`) |
| `ideal_answer` | string | example of a stronger answer, revealed only now (`ev.ideal`); the UI labels it "Example — not your answer" |
| `feedback_source` | `"rules"` | always `rules` in the MVP (D4); `"genai"` is reserved for a possible later integration; the UI ignores it |
| `scoring_version` | string | identifies the scoring configuration used, for reproducibility |
| `created_at` | timestamp | |

```json
{
  "id": "e2d7f4a9-6c18-4b05-8d93-0a5b1c7e3f26",
  "question_id": "0a7c5e31-2d94-4c1b-b6f8-3e9a1d5c7b02",
  "overall_score": 82,
  "category_scores": { "relevance": 86, "clarity": 79, "technical_depth": 77, "structure": 81 },
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
- **AI/ML:** a **local** sentence-embedding model measures semantic similarity to the reference answer, and **explicit criteria** (key-point coverage, structure cues, clarity cues) are computed by deterministic rules; feedback text comes from templates — Section 16.4. No external service is called.
- **Important limits (D5):** the scores are *automated estimates* from a method that has **not been validated** (Section 16.8–16.9). Semantic similarity is **not a complete measure of answer quality**, and none of the categories measures psychological confidence. All scoring happens here on the backend; the frontend never supplies a score.
- **Degradation policy:** if the similarity model is not loaded (and `SIMILARITY_BACKEND=sbert`), E22 reports `unavailable` and this call returns `AI_SERVICE_UNAVAILABLE` (503, `retryable: true`). The service **never silently switches** to a different scoring method; the lexical backend is a separate, deliberately chosen configuration with its own `scoring_version` (Section 16.6).
- **Latency:** the model is loaded at start-up, so a request never triggers a model download or load. The actual latency on the team's machines is **not yet measured** (OD-13); there is no gateway timeout in the local setup.

### E17 — `GET /api/v1/interviews/{interview_id}/questions/{question_id}/evaluation`

- **Purpose:** fetch a stored evaluation (recovery after refresh or a lost response). **Auth:** current user (Section 5).
- **Response `200 OK`:** same body as E16. **Errors:** `EVALUATION_NOT_FOUND` (404), `QUESTION_NOT_FOUND` (404), `INTERVIEW_NOT_FOUND` (404).
- **Database:** read `evaluations`.

---

## 11. Results API

### E18 — `GET /api/v1/interviews/{interview_id}/results`  (frontend: `getInterviewResults`)

E14 returns exactly this payload when an interview is completed.

- **Purpose:** the complete results for one completed interview.
- **Auth:** current user — the seeded demo user in the MVP, a Bearer token once authentication is enabled (Section 5).
- **Response fields**

| Field | Type | UI use |
| --- | --- | --- |
| `interview` | InterviewSummary | header card (`meta`): `id, completed_at, target_role, interview_type, difficulty, question_count, overall_score, status` |
| `breakdown.structure` / `.relevance` / `.clarity` / `.technical_depth` / `.communication` | integer 0–100 | "Performance breakdown" bars; `technical_depth` is shown as *Technical Knowledge* here (F8); `structure` is shown as *Structure* (it replaces *Confidence*, FC-13) |
| `additional_strength` | string | third item under "Strengths" (`extraStrength`) |
| `additional_improvement` | string | third item under "Areas for improvement" (`extraImprovement`) |
| `recommendations` | string[3] | "AI recommendations" |
| `generated_by` | `"rules"` | provenance of the three strings above; always `rules` in the MVP (`"genai"` reserved) |
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
| `breakdown.communication` | round-half-up of `(breakdown.clarity + breakdown.structure) / 2`, using the **already rounded** values (as the frontend does) |
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
  "breakdown": { "structure": 83, "relevance": 88, "clarity": 81, "technical_depth": 79, "communication": 82 },
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
        "category_scores": { "relevance": 92, "clarity": 85, "technical_depth": 83, "structure": 87 },
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
- **Auth:** current user — the seeded demo user in the MVP, a Bearer token once authentication is enabled (Section 5).
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
- **Auth:** current user — the seeded demo user in the MVP, a Bearer token once authentication is enabled (Section 5).
- **Definition:** each skill is the round-half-up mean, over the user's completed interviews, of that interview's `breakdown` value (every interview weighs equally). Skills: `communication`, `relevance`, `structure`, `clarity`, `technical_depth`.
- **Ordering:** by `score` descending; ties broken in the fixed order listed above (the Dashboard shows the first four, F7).
- **Response `200 OK`**

| Field | Type | Notes |
| --- | --- | --- |
| `skills[]` | array | `{ key, label, score }` |
| `skills[].label` | string | `Communication`, `Relevance`, `Structure`, `Clarity`, `Technical Depth` |
| `interviews_counted` | integer | |

```json
{
  "skills": [
    { "key": "communication", "label": "Communication", "score": 88 },
    { "key": "relevance", "label": "Relevance", "score": 86 },
    { "key": "structure", "label": "Structure", "score": 82 },
    { "key": "clarity", "label": "Clarity", "score": 81 },
    { "key": "technical_depth", "label": "Technical Depth", "score": 76 }
  ],
  "interviews_counted": 4
}
```

- **Empty state:** a user with no completed interviews gets `{ "skills": [], "interviews_counted": 0 }`. **The current frontend cannot handle this** (F26).
- **Status codes:** 200 · 401 · 503. **Database:** read `user_performance`. **AI/ML:** none.

### E21 — `GET /api/v1/performance/summary`

- **Purpose:** the figures the Dashboard and Performance page currently compute client-side (F6), without loading the whole history. **Auth:** current user (Section 5).
- **Query:** `trend_limit` (integer, default 12, max 50).
- **Response `200 OK`**

| Field | Type | Notes |
| --- | --- | --- |
| `interviews_completed` | integer | "Interviews completed" |
| `average_score` | integer \| null | round-half-up mean of overall scores; this is the Dashboard's "Average confidence" figure, to be relabelled "Average score" (F16, FC-13); `null` if none |
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

- **Purpose:** the signed-in user (replaces the hard-coded `DEMO_USER`; in demo mode it returns the seeded demo user, so the welcome message, avatar initials and the "Sign in as {name}" button keep working). **Auth:** current user (Section 5).
- **Response `200 OK`:** `{ "id": uuid, "name": string, "email": string, "created_at": timestamp }`

```json
{ "id": "3f2b8c1e-7d4a-4e59-9c0b-2a1f6e8d4b10", "name": "Alex Morgan",
  "email": "alex.morgan@email.com", "created_at": "2026-10-08T09:12:44Z" }
```

- **Errors:** `UNAUTHORIZED` (401), `TOKEN_EXPIRED` (401). **Database:** read `users`.

### E06 — `PATCH /api/v1/users/me`  (frontend: `updateProfile`)

- **Purpose:** save the Profile form. **Auth:** current user (Section 5).
- **Request body (JSON)** — at least one field:

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `name` | string | no | trimmed, 2–100 chars (UI minimum 2) |
| `email` | string | no | valid email, unique. In demo mode no verification is needed; whether a real account must re-verify a changed email is a Phase 2 question (OD-1 residual) |

```json
{ "name": "Alex Morgan", "email": "alex.m@email.com" }
```

- **Response `200 OK`:** the updated user (same shape as E05). The UI replaces its `user` state with it.
- **Status codes:** 200 · 401 · 409 · 422 · 503
- **Errors:** `VALIDATION_ERROR` (422), `EMAIL_ALREADY_IN_USE` (409), `UNAUTHORIZED` (401)
- **Database:** update `users.name`, `users.email`, `updated_at`.
- **Related:** the "Reset demo data" button maps to E23 (development-only). Real account and data deletion is a future endpoint (Section 22).

---

## 15. Database Models

**[Decided D2]** The primary database is **PostgreSQL running locally** on the developer's machine (no paid subscription). The configuration is **portable**: the connection comes from a single `DATABASE_URL`, so the same code can later point at AWS RDS **if** the AWS Academy environment permits (D8). Types below are written generically.

| Generic | PostgreSQL (primary) | SQLite (temporary fallback only) |
| --- | --- | --- |
| `UUID` | `uuid` | `CHAR(36)` text |
| `TIMESTAMPTZ` | `timestamptz` | text/`DATETIME`, stored as UTC |
| `JSONB` | `jsonb` | `JSON` (text) |
| `SMALLINT` / `INTEGER` / `BOOLEAN` / `TEXT` / `VARCHAR(n)` | same | same (`BOOLEAN` is stored as 0/1) |

**Portability rules [Recommended]** so the fallback stays possible without a rewrite: use SQLAlchemy's generic `Uuid`, `JSON` and `DateTime(timezone=True)` types; avoid PostgreSQL-only features (`ARRAY`, JSONB operators, extensions such as vector types); keep `CHECK` constraints and foreign keys; manage schema only through migrations.

**SQLite fallback policy.** SQLite is a *documented temporary development fallback*, to be used **only** if local PostgreSQL cannot be installed or run and the blocker is recorded. Using it does **not** change the primary decision. Known limits when using it: foreign keys must be switched on per connection, `ALTER TABLE` support is partial (migrations need batch mode), there is no real concurrency, and behaviour of `CHECK`/date handling can differ from PostgreSQL — so anything that passes only on SQLite is not considered verified.

Nothing here has been created; this is a design for the Database Engineer (Ahmed Hamdy Ahmed) to review.

### 15.1 Entity relationships

```
User (users)
  │
  ├── RefreshToken (refresh_tokens)          1 : N   [Phase 2 only — not created in the MVP]
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
                                 interview_questions.bank_question_id   [required for the MVP, D4]
```

### 15.2 Tables

Legend: **PK** primary key · **FK** foreign key · *Req* = NOT NULL.

#### `users`

| Field | Type | Req | Key | Notes |
| --- | --- | --- | --- | --- |
| `id` | UUID | yes | PK | |
| `name` | VARCHAR(100) | yes | | |
| `email` | VARCHAR(254) | yes | unique | stored lower-case |
| `password_hash` | VARCHAR(255) | no | | `NULL` in demo mode (D3); used from Phase 2 |
| `is_active` | BOOLEAN | yes | | default `true` |
| `created_at` / `updated_at` | TIMESTAMPTZ | yes | | |

#### `refresh_tokens`  *(Phase 2 — not created in the MVP)*

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
| `storage_backend` | VARCHAR(8) | yes | | `local` (MVP) or `s3` (later) — says how to interpret `storage_key` |
| `storage_key` | VARCHAR(512) | yes | | **relative** key (random, not derived from the filename): a path under the private CV directory for `local`, an object key for `s3` |
| `extracted_text` | TEXT | no | | full text; cleared on delete |
| `parse_status` | VARCHAR(16) | yes | | `parsed` (MVP); reserved: `processing`, `failed` |
| `created_at` | TIMESTAMPTZ | yes | | |
| `deleted_at` | TIMESTAMPTZ | no | | soft-delete marker while the stored file is being removed |

#### `cv_profiles`  *(rule-based extraction; shape provisional, OD-15)*

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
| `source` | VARCHAR(16) | yes | | `rules` in the MVP (`genai` reserved) |

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
| `question_source` | VARCHAR(8) | yes | | `bank` in the MVP (`genai` reserved) |
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
| `ideal_answer` | TEXT | yes | | snapshot of the bank's reference answer; never returned before evaluation |
| `key_points` | JSONB | yes | | snapshot of the bank entry's expected key points (array of short strings); used by the scoring criteria; never returned |
| `source` | VARCHAR(8) | yes | | `bank` in the MVP (`genai` reserved) |
| `bank_question_id` | UUID | no | FK → `question_bank.id` ON DELETE SET NULL | only when drawn from the bank |
| `created_at` | TIMESTAMPTZ | yes | | |

#### `answers`

| Field | Type | Req | Key | Notes |
| --- | --- | --- | --- | --- |
| `id` | UUID | yes | PK | |
| `question_id` | UUID | yes | FK → `interview_questions.id` ON DELETE CASCADE, **unique** | one answer per question |
| `answer_text` | TEXT | yes | | 30–1500 chars at write time |
| `char_count` | INTEGER | yes | | |
| `input_mode` | VARCHAR(8) | yes | | `text`; `speech` reserved (Whisper deferred, D6) |
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
| `structure_score` | SMALLINT | yes | | CHECK 0–100 (replaces the former confidence score, D5) |
| `semantic_similarity` | NUMERIC(5,4) | no | | raw model output, kept for calibration against human ratings; **not** exposed by the API |
| `strengths` | JSONB | yes | | array of 1–3 strings |
| `weaknesses` | JSONB | yes | | array of 1–3 strings |
| `improvement_tip` | TEXT | yes | | |
| `feedback_source` | VARCHAR(8) | yes | | `rules` in the MVP |
| `scoring_version` | VARCHAR(30) | yes | | |
| `model_info` | JSONB | yes | | model name/version and criteria configuration used (for example the embedding model id and `SIMILARITY_BACKEND`) |
| `latency_ms` | INTEGER | no | | for local logging/analysis |
| `created_at` | TIMESTAMPTZ | yes | | |

#### `interview_results`

| Field | Type | Req | Key | Notes |
| --- | --- | --- | --- | --- |
| `interview_id` | UUID | yes | PK, FK → `interviews.id` ON DELETE CASCADE | 1 : 1 |
| `overall_score` | SMALLINT | yes | | duplicate of `interviews.overall_score` written in the same transaction |
| `structure_score`, `relevance_score`, `clarity_score`, `technical_depth_score`, `communication_score` | SMALLINT | yes | | the five `breakdown` values |
| `additional_strength` | TEXT | yes | | |
| `additional_improvement` | TEXT | yes | | |
| `recommendations` | JSONB | yes | | array of 3 strings |
| `generated_by` | VARCHAR(8) | yes | | `rules` in the MVP |
| `created_at` | TIMESTAMPTZ | yes | | |

#### `user_performance`

| Field | Type | Req | Key | Notes |
| --- | --- | --- | --- | --- |
| `id` | UUID | yes | PK | |
| `user_id` | UUID | yes | FK → `users.id` ON DELETE CASCADE | |
| `skill_key` | VARCHAR(20) | yes | | CHECK in (`communication`,`relevance`,`structure`,`clarity`,`technical_depth`); **unique with `user_id`** |
| `score` | SMALLINT | yes | | 0–100 |
| `interviews_counted` | INTEGER | yes | | |
| `updated_at` | TIMESTAMPTZ | yes | | |

Maintained inside the E14 transaction by **recomputing from the user's `interview_results`** rather than incrementing, so values cannot drift. For the capstone data volume this table could equally be a view; a table was chosen so the read path of E20 is trivial.

#### `question_bank`  *(reference data — required for the MVP, D4)*

The curated source of questions and reference answers. It is **not user data**: it is seeded by the team from a version-controlled file and shared by all interviews.

| Field | Type | Req | Key | Notes |
| --- | --- | --- | --- | --- |
| `id` | UUID | yes | PK | |
| `kind` | VARCHAR(14) | yes | | `generic` (a fixed question) or `skill_template` (contains a `{skill}` placeholder filled from the CV) |
| `text` | TEXT | yes | | question text, or the template |
| `question_type` | VARCHAR(10) | yes | | `technical` / `behavioral` |
| `difficulty` | VARCHAR(12) | yes | | `beginner` / `intermediate` / `advanced` |
| `role_tags` | JSONB | yes | | e.g. `["AI Engineer","Data Scientist"]`; the value `"general"` marks role-agnostic entries |
| `skill_tags` | JSONB | yes | | skills this question is about; used to rank against the CV's skills |
| `reference_answer` | TEXT | yes | | curated answer, written to stay well under the model's 256-word-piece limit (Section 8.3) |
| `key_points` | JSONB | yes | | 3–6 short phrases a good answer should cover; used by the criteria scoring |
| `reference_embedding` | JSON | no | | precomputed embedding of `reference_answer` (a list of numbers) so it need not be recomputed per request; **no vector extension or vector database is required** |
| `embedding_model` | VARCHAR(100) | no | | model id that produced `reference_embedding`; if the configured model differs the embedding is recomputed |
| `source_note` | VARCHAR(255) | no | | who wrote it / licence / attribution (OD-14) |
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
| Delete CV (E10) | `cvs` row, the stored file, `cv_profiles`, `cv_skills` removed; `interviews.cv_id` → `NULL`; interviews, answers, evaluations and results remain |
| Abandon interview (E13) | status → `abandoned`; rows kept; excluded from history/results/performance |
| Delete user (future) | cascades to everything above |
| Retention period for CVs and answers | local development: data stays until deleted (E10, E23) and never leaves the machine; a retention policy for any public deployment is **[Open]** (OD-10) |

---

## 16. AI/ML Pipeline

**Status: design only. Nothing in this section has been implemented, run or validated.** It assigns every intelligent or computed step to exactly one of four classes so responsibilities and failure handling are unambiguous. The MVP uses **no paid or external AI service** (D4) and **one local model** (D5).

| Class | Meaning | Typical failure handling |
| --- | --- | --- |
| **[D] Deterministic** | ordinary backend logic with a fixed, testable outcome | bug → `500`; never "retried into a different answer" |
| **[ML] Local model** | local inference with Sentence Transformers (candidate `all-MiniLM-L6-v2`) | model not loaded → `AI_SERVICE_UNAVAILABLE`; never silently replaced |
| **[DB] Database** | reads/writes in PostgreSQL | `DATABASE_UNAVAILABLE` (503) |
| *GenAI* | external LLM (OpenAI API / Amazon Bedrock) | **not part of the MVP** (D4); see 16.5 |

### 16.1 Pipeline steps

"Basis": **[Proposal]** explicit in the proposal; **[Decided]** from D1–D8; **[Recommended]** introduced here; **[Open]** unresolved.

| Step | Task | Class | Input → Output | Basis |
| --- | --- | --- | --- | --- |
| **A** | CV file → plain text | [D] | validated PDF/DOCX → `extracted_text` | **[Proposal]** "converted to text"; free libraries **[Decided D7]** |
| **B** | CV text → skills (and best-effort experience/education/project lines) | [D] | `extracted_text` → `cv_skills`, `cv_profiles` | **[Decided D4/D7]** no GenAI → rule-based match against a curated skills list; list source **[Open]** OD-15 |
| **C** | CV + role + type + difficulty → *n* questions | [D] (optional [ML] ranking) | CV skills, config → question list | **[Decided D4]** selection from the curated bank (E11 rules); reduced form of the proposal's "personalized questions" |
| **D** | each selected question → reference answer and key points | [D] | `question_bank` entry → snapshot in `interview_questions` | **[Decided D4]** curated reference answers replace GenAI "ideal answers" |
| **E** | candidate answer vs reference answer → semantic similarity | [ML] | answer chunks + reference embedding → similarity values | **[Proposal]** "semantic similarity against ideal responses"; local model **[Decided D5]** |
| **F** | answer → explicit criteria signals (key-point coverage, structure cues, clarity cues, specificity) | [D] | answer, key points → numbers 0–1 | **[Decided D5]** "combine similarity with explicit criteria"; the criteria themselves **[Recommended]** |
| **G** | signals → category scores and overall score | [D] | signals + config constants → integers 0–100 | **[Recommended]**; constants and weights **[Open]** (OD-8) |
| **H** | scores → strengths, weaknesses, improvement tip | [D] templates | scores, missing key points → text | **[Decided D4]** transparent rule-based templates |
| **I** | all evaluations → overall score and breakdown | [D] | evaluations → `interview_results` numbers | **[Recommended]** formulas in Section 11 (mirror the frontend) |
| **J** | breakdown → 3 recommendations and 2 highlight strings | [D] templates | breakdown → text | **[Decided D4]** rule-based |
| **K** | interview results → user skill scores | [D] + [DB] | `interview_results` → `user_performance` | **[Recommended]** |

**Deferred (not in the MVP):** speech-to-text with Whisper (D6) · BERT/DistilBERT scoring heads · GenAI question, ideal-answer and feedback generation (D4) · GenAI follow-up questions (F21).

### 16.2 Where each step runs

```
E07  CV upload ───────────────►  A [D]  ─►  B [D rules]  ─►  [DB] cvs, cv_profiles, cv_skills
                                                              + private file storage

E11  Create interview ────────►  [DB] load CV skills, question_bank
                                 C [D selection (+ optional ML ranking)]  ─►  n questions
                                 D [D] copy reference answer + key points (snapshot)
                                 [DB] interviews, interview_questions

E15  Submit answer ───────────►  [D] validate length  ─►  [DB] answers

E16  Evaluate answer ─────────►  [DB] read answer + reference + key points
                                 E [ML] chunk answer, embed, similarity
                                 F [D] criteria signals
                                 G [D] category + overall scores   ← computed ONLY here
                                 H [D] strengths / weaknesses / tip (templates)
                                 [DB] evaluations

E14  Complete interview ──────►  [DB] read evaluations
                                 I [D] aggregate  ─►  J [D] recommendation templates
                                 [DB] interview_results, interviews, user_performance (one transaction)
```

### 16.3 Question source (MVP): curated bank, no generation **[Decided D4]**

| Aspect | MVP behaviour |
| --- | --- |
| Source | `question_bank` rows seeded from a version-controlled file, each with a reference answer and key points (Section 15, Section 8.3) |
| Selection | deterministic rules in E11 (type, role tags, difficulty, CV skills, uniqueness, no partial interviews) |
| "CV-aware" | `skill_template` entries are instantiated with a skill found in the CV; skill-overlapping entries rank higher. This **tailors selection**; it does not generate new questions |
| Optional ranking | if the embedding model is loaded, similarity between the CV's skills and `skill_tags` / question text may break ties; it must never be required |
| RAG | only the retrieval half (finding relevant bank entries). RAG *with generation* is deferred |
| Open items | bank authorship, size, licensing and role coverage (OD-14); skills-list source (OD-15) |

### 16.4 Evaluation design (MVP) **[Decided D5; details Recommended and unvalidated]**

**Principle.** The score is a *transparent combination of one semantic-similarity signal and several explicit, inspectable criteria*. Every number can be traced to a rule. It is an estimate for practice, not an assessment of the person, and **it does not measure psychological confidence** (nor personality, delivery, honesty or hiring suitability).

**Pre-processing.** Trim; normalise whitespace; split into sentences with simple rules; form **chunks** of up to about three consecutive sentences (overlapping by one sentence) so every chunk is far below the model's 256-word-piece limit (16.6). Answers are at most 1500 characters, so a handful of chunks at most.

**Signals** (each is a number between 0 and 1):

| Signal | How it is computed | Class |
| --- | --- | --- |
| `sim_ref` | cosine similarity between each answer chunk and the reference answer's embedding; aggregated by the maximum, or the mean of the top two (choice fixed by experiment) | [ML] |
| `sim_question` | cosine similarity between the chunks and the question text — an *off-topic guard* | [ML] |
| `keypoint_coverage` | fraction of the entry's `key_points` that the answer covers: a key point counts as covered if its words appear (after simple normalisation) **or** a chunk is semantically close to it above a threshold | [D] + [ML] |
| `structure_cues` | presence of cue groups: context/problem, action/approach, result/outcome (numbers and outcome words count), and an ordered flow (first/then/finally style connectors); for behavioural questions the groups follow STAR | [D] |
| `clarity_cues` | answer length inside a target band for its question type; average sentence length inside a band; low repetition of the same phrases | [D] |
| `specificity` | counts of concrete details: numbers/percentages, named tools or technologies (matched against the entry's `skill_tags` and the CV's skills) | [D] |

**Category scores** (integers 0–100, higher is better; labels as shown in the UI):

| Category (API key) | UI label | Built from |
| --- | --- | --- |
| `relevance` | Relevance | `sim_ref`, capped when `sim_question` is below the off-topic threshold |
| `technical_depth` | Technical Depth | mainly `keypoint_coverage`, plus `specificity`. For behavioural questions it means *depth and specificity of the example* — the UI label is unchanged |
| `structure` | Structure *(replaces "Confidence")* | `structure_cues` |
| `clarity` | Clarity | `clarity_cues` |

`overall_score` = the weighted mean of the four categories. **Every constant** — similarity-to-score mapping bounds, thresholds, band limits, weights (initially equal, a placeholder) — lives in one versioned configuration and is identified by `scoring_version`. The similarity mapping is a configurable clamped linear map `clamp((x − low) / (high − low)) × 100`; `low` and `high` are **to be chosen by experiment** (16.9) and no values are claimed here. Changing any constant means a new `scoring_version`; stored evaluations are never recomputed, so old and new versions are never mixed silently.

**Feedback templates (step H).** A fixed library maps *(criterion, level)* to a sentence, so every sentence shown can be explained by a rule.

- *Strengths*: up to 3, from the highest-scoring criteria at or above a "strong" threshold.
- *Weaknesses*: up to 3, from the lowest-scoring criteria below a "weak" threshold; they may name **up to two missing key points** from the bank ("You did not mention: …").
- *Guarantee*: 1–3 of each (the UI renders every item). If nothing reaches "strong", the best criterion's mild-praise template is used; if nothing is "weak", the lowest criterion's "minor improvement" template is used.
- *Tip*: one template chosen by the weakest criterion (for example low structure → a STAR reminder).
- Templates never state that an answer is *correct* or *incorrect*; they describe coverage, structure and clarity.

**Interview-level text (steps I–J).** Breakdown values and `communication = round-half-up((clarity + structure) / 2)` are computed as in Section 11. The three `recommendations` come from templates for the three weakest categories (one each); `additional_strength` and `additional_improvement` come from the strongest and weakest categories. All of this is static text selected by rules; none of it is generated.

### 16.5 Generative AI: deferred, optional future integration **[Decided D4]**

No OpenAI, Bedrock or other API is required for the MVP, so there are **no AI API keys, no per-call cost and no CV text sent anywhere**. If GenAI is added later it is purely additive: `question_source` / `feedback_source` / `generated_by` would gain the value `genai` (already reserved in the schema), behind one provider-agnostic adapter, with rule-based text as the fallback. A later integration would need its own review of: provider and model choice, prompt-injection handling (CV text and answers are untrusted input), data minimisation (strip contact details), provider retention terms, cost limits, and structured-output validation. None of that is designed in detail here because it is out of scope.

### 16.6 Local model, serving and machine compatibility **[Decided D5]**

**Candidate model: `sentence-transformers/all-MiniLM-L6-v2`** (the decision's initial candidate). Facts checked against its published model information:

| Fact | Consequence |
| --- | --- |
| produces 384-dimensional embeddings; about 22.7 million parameters | small and fast enough for CPU use |
| **input longer than 256 word pieces is truncated** | answers (up to 1500 characters) can exceed it → the **chunking** in 16.4 is mandatory, and reference answers must be short (Section 8.3) |
| presented by its authors as a sentence and short-paragraph encoder | suited to short answers; long essays are out of scope |
| general-purpose; reported to be weaker on specialised domains | technical interview vocabulary may be handled less well — to be **tested, not assumed** (16.9) |
| intended for English text | interviews are English-only in the MVP; other languages are unsupported and unvalidated |

The model is **a candidate, not a validated choice**. If testing shows it is inadequate, it is replaceable behind the similarity-engine interface.

**Serving.**

- Loaded **once at start-up** in the FastAPI process; E22 reports it as ready only after loading. A request never triggers a download or load.
- The first run needs internet access once to download the model files into the local cache; afterwards it works offline. For a fully offline machine the model folder can be copied and referenced with `EMBEDDING_MODEL_PATH`.
- Embeddings of bank reference answers are computed once (seed step or first start) and stored in `question_bank.reference_embedding` together with `embedding_model`; if the configured model changes they are recomputed.
- `evaluations.model_info` records the model id and `SIMILARITY_BACKEND`; `scoring_version` records the constants.

**Compatibility with the development machine ("if compatible").** Requirements: 64-bit OS; **Python 3.12 recommended** (all planned packages support it; Section 25.2); enough free disk for PyTorch and its dependencies — a **large download** (the default Linux build can bundle GPU libraries, CPU-only builds are smaller; check before installing); no GPU needed. A **one-line compatibility check** is the first AI task (Section 26, step 8): encode two sentences and print their cosine similarity. If it fails, record the blocker rather than guessing.

**Explicit fallback — `SIMILARITY_BACKEND=lexical`.** If the machine cannot run the model, a deliberately selected, dependency-free lexical backend (term-overlap similarity against the reference and key points, standard library only) can run the same pipeline. It is clearly lower quality, produces its own `scoring_version`, shows as `"lexical"` in E22, and its results are **not comparable** with `sbert` results. It is never chosen automatically: with `SIMILARITY_BACKEND=sbert`, a load failure keeps the service *not ready* (consistent with D2's rule against silently changing a primary decision).

**Deferred model work:** BERT/DistilBERT scoring heads, fine-tuning, and any cross-encoder — none is part of D5.

### 16.7 Responsibility matrix per operation

| Operation | Deterministic | Local model | Database |
| --- | --- | --- | --- |
| E07 upload CV | validation, text extraction, skill rules | — | `cvs`, `cv_profiles`, `cv_skills`, private file |
| E11 create interview | validation, selection, template filling | optional ranking | `interviews`, `interview_questions` (reads `question_bank`) |
| E15 submit answer | length rules | — | `answers` |
| E16 evaluate | chunking, criteria, scoring, templates | similarity | `evaluations` |
| E14 complete | aggregation, formulas, recommendation templates | — | `interview_results`, `user_performance`, `interviews` |
| E18–E21 reads | ordering, formatting | — | reads only |

### 16.8 What the scores mean — and do not mean

**Status: not validated.** Until the plan in 16.9 has been run and its results written down, the application and its documentation must describe scores as *automated estimates for practice*, not as accurate assessments.

1. Semantic similarity measures how close an answer's **meaning and topic** are to a reference answer. It does **not** verify factual correctness: a fluent, wrong answer on the right topic can score well.
2. The reference is **one example**, not the only right answer. A correct answer with a different approach or vocabulary can score low.
3. Verbose answers that mention many related terms can score well without substance; short, precise answers can score low. Chunking and the criteria reduce, but do not remove, this.
4. The model truncates beyond 256 word pieces; chunking avoids silent loss but changes the numbers and must be tested.
5. Interviews are English only; other languages are unsupported.
6. A general-purpose model may handle specialised technical vocabulary poorly.
7. The rule-based criteria are **proxies** (cue words, lengths, counts). They can misfire on unusual phrasing and can be gamed.
8. Key-point coverage is only as good as the curated key points.
9. **Nothing here measures psychological confidence, personality, spoken delivery or suitability for a job.** Scores must not be used for hiring or grading decisions.
10. Scores from different `scoring_version`s (or from the `lexical` backend) are not comparable.

### 16.9 Validation plan (to be executed; nothing has been run)

The proposal's own metric — correlation between the AI score and human-rated benchmarks — is kept as the acceptance test.

| Step | What to do | Output |
| --- | --- | --- |
| V1 | **Smoke tests:** a reference answer scores high on relevance and coverage; an unrelated paragraph scores low (off-topic guard); an empty or too-short answer is rejected before scoring; the same input gives the identical result twice; a 1500-character answer produces several chunks without error | pass/fail list |
| V2 | **Property checks:** adding a missing key point never lowers coverage; repeating the same sentence does not raise the score beyond a stated bound | pass/fail list |
| V3 | **Human-rated set:** collect a small set of sample answers (the team chooses the size, for example a few dozen), have at least two teammates rate each independently on a fixed scale, compute inter-rater agreement and the correlation (for example Spearman) between `overall_score` and the mean human rating | numbers, including weak ones |
| V4 | **Calibrate on one subset, report on another** to avoid reporting an overfitted result; adjust `low`/`high` and weights only on the calibration subset | new `scoring_version` |
| V5 | **Write the result down** (model id, `scoring_version`, data description, correlation, failure examples) and limit every claim in the README and UI to what the report supports | `evaluation_report` document |

The team must fix the acceptance threshold *before* running V3; this specification deliberately does not pick one (OD-8 residual).

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
| `feedback_source` / `generated_by` / `question_source` | `rules` (feedback, results text) · `bank` (questions) — `genai` is reserved for a possible later integration | not displayed |
| `skill_key` | `communication`, `relevance`, `structure`, `clarity`, `technical_depth` | `Communication`, `Relevance`, `Structure`, `Clarity`, `Technical Depth` |

### 17.2 Shared objects

| Schema | Fields |
| --- | --- |
| **User** | `id` uuid · `name` string · `email` string · `created_at` timestamp |
| **CV** | `id` uuid · `original_filename` string · `extension` `pdf`\|`docx` · `size_bytes` int · `parse_status` string · `created_at` timestamp |
| **CVExtracted** | `skills` string[] · `experience` string[] · `education` string[] · `projects` string[] |
| **InterviewConfig** | `cv_id` uuid · `target_role` string · `interview_type` enum · `difficulty` enum · `question_count` int |
| **Question** | `id` uuid · `position` int · `text` string · `type` enum (+ `state` in E12) |
| **Answer** | `id` uuid · `interview_id` uuid · `question_id` uuid · `answer_text` string · `char_count` int · `input_mode` string · `submitted_at` / `updated_at` timestamp |
| **CategoryScores** | `relevance` · `clarity` · `technical_depth` · `structure` — integers 0–100 |
| **Evaluation** | `id` · `question_id` · `overall_score` int · `category_scores` CategoryScores · `strengths` string[1..3] · `weaknesses` string[1..3] · `improvement_tip` string · `ideal_answer` string · `feedback_source` enum · `scoring_version` string · `created_at` timestamp |
| **InterviewSummary** (`interview` in results) | `id` · `completed_at` · `target_role` · `interview_type` · `difficulty` · `question_count` · `overall_score` · `status` |
| **Breakdown** | `structure` · `relevance` · `clarity` · `technical_depth` · `communication` — integers 0–100 |
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
| `ev.cats` | `category_scores` | keys in this order: `Relevance`, `Clarity`, `Technical Depth`, `Structure`. **The adapter must not relabel `structure` as "Confidence"** — that would reintroduce the claim D5 forbids; the UI code that reads the key `Confidence` changes instead (FC-13) |
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
  "cats": { "Relevance": 86, "Clarity": 79, "Technical Depth": 77, "Structure": 81 },
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
| `request_id` | string | also sent as `X-Request-ID`; correlates with the server logs |

A `success: false` flag is omitted on purpose: the HTTP status already says so and an extra boolean could contradict it.

### 18.2 Error catalog

| Code | HTTP | When | Endpoints |
| --- | --- | --- | --- |
| `VALIDATION_ERROR` | 422 | malformed body/query/path (generic) | all |
| `UNAUTHORIZED` | 401 | missing or invalid credentials/token — **only once authentication is enabled (Phase 2); in demo mode no endpoint returns 401** | all protected |
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
| `AI_SERVICE_UNAVAILABLE` | 503 | the local similarity model is not loaded or failed (there is no GenAI provider in the MVP) | E16 |
| `AI_SERVICE_TIMEOUT` | 504 | evaluation exceeded its configured time budget (`EVALUATION_TIMEOUT_SECONDS`) | E16 |
| `STORAGE_UNAVAILABLE` | 503 | private file storage failed (disk full or permissions locally; S3 later) | E07, E10, E23 |
| `QUESTION_BANK_INSUFFICIENT` | 422 | the curated bank cannot supply the requested number of questions for this combination | E11 |
| `NOT_FOUND` | 404 | the route does not exist — including E01–E04 in demo mode and E23 outside development | any |
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
| `TOKEN_EXPIRED` *(Phase 2)* | not handled | call E03 once, retry the original request once |
| `UNAUTHORIZED`, `TOKEN_INVALID` *(Phase 2)* | not handled | clear session, go to sign-in |
| `retryable: true` | no retry hint | show the existing "try again" state; answer text is already preserved by the UI |
| `RATE_LIMITED` | not handled | respect `Retry-After` |
| Network error / timeout | none | add a client-side timeout so a stalled call becomes a normal error |

---

## 19. Security Requirements

Requirements only — none is implemented. IDs allow tracing in reviews. Because the MVP is **local and single-user** (D1, D3) and uses **no external AI service** (D4), some requirements apply only later; section 19.0 says which.

### 19.0 When each requirement applies

| Phase | Requirements |
| --- | --- |
| **Local MVP — must hold from the first line of code** | S-02, S-03, S-06 – S-10, S-12, S-13, S-15, S-16, S-18, S-20, S-22, S-24, S-27, S-31 – S-34 |
| **Before any public deployment exposes private data** (D3, D8) | S-01, S-04, S-05, S-19, S-21, S-23, S-26, S-28 – S-30 and the whole of Phase 2 authentication (Section 5.4) |
| **Only if GenAI is added later** | S-14, S-17, S-25 (and review of provider terms, OD-10) |
| **Recommended hardening, not required for the MVP** | S-11 |

A key privacy property of the MVP: **CV text and answers never leave the developer's machine** — no external API is called.

### 19.1 Authentication and authorization

| ID | Requirement |
| --- | --- |
| S-01 | *(Phase 2)* Every endpoint except register, login, refresh and health requires a valid access token. In the local MVP the single demo user is resolved by `get_current_user` instead (Section 5.2). |
| S-02 | **Object-level authorization:** every query on CVs, interviews, questions, answers, evaluations and results is filtered by the current `user_id`, even in demo mode. Foreign or unknown IDs return `404`, never `403`, so IDs cannot be probed. |
| S-03 | **Never trust client-supplied scores or aggregates.** E14 ignores the `items` the frontend currently sends (F4); every score is computed on the backend (D5). No endpoint accepts a score as input. |
| S-04 | *(Phase 2)* If passwords are used: argon2id or bcrypt, per-user salt, never logged or returned; login responses must not reveal whether an email exists. |
| S-05 | *(Public deployment)* Rate limiting per user and per IP, strictest on login, E07 (parsing cost) and E16 (compute cost). |

### 19.2 CV file handling

| ID | Requirement |
| --- | --- |
| S-06 | Allowed types: PDF and DOCX only. Reject `.doc`, `.docm`, `.dotm` and anything else. |
| S-07 | Validate the **content signature** (PDF header; DOCX is a ZIP containing `[Content_Types].xml` and `word/document.xml`), not just the extension or the client's `Content-Type`. |
| S-08 | Maximum size 5 MB (5 × 1024 × 1024 bytes), enforced while reading the upload (abort early). If a gateway is added later it must not allow more than its own ceiling (Section 20). |
| S-09 | Defend against decompression bombs and malformed files: cap uncompressed DOCX size and entry count; reject encrypted PDFs; apply a parse timeout; never evaluate macros or embedded content. |
| S-10 | Sanitise the filename; store under a **random name**; never build paths from user input; never execute uploaded files and never serve them back to browsers. |
| S-11 | Antivirus scanning of uploads is a **recommended hardening** (future). |

### 19.3 Input validation and untrusted text

| ID | Requirement |
| --- | --- |
| S-12 | Validate every request with strict typed schemas (enums, lengths, formats) and reject unknown fields where feasible. Limit JSON body size. |
| S-13 | All SQL through an ORM / parameterised queries. |
| S-14 | *(Only if GenAI is added)* CV text and answers are **untrusted input to language models** (prompt injection): delimit them in prompts, validate model output against schemas, never let model output drive actions (Section 16.5). |
| S-15 | Responses are JSON only; stored free text is returned as data, never as markup. The frontend renders it as text (React escapes by default). |

### 19.4 Secrets and configuration

| ID | Requirement |
| --- | --- |
| S-16 | Configuration comes from **environment variables** (a local `.env` file that is **git-ignored**, with a committed `.env.example` that contains no real values). The database password and, later, the JWT signing key are never committed. |
| S-17 | *(Only if GenAI is added)* AI provider keys exist **only on the backend**; the frontend never receives or embeds them. There are none in the MVP. |
| S-18 | Separate configuration per environment (`APP_ENV`); rotate any credential that has been exposed. |

### 19.5 Transport, CORS and headers

| ID | Requirement |
| --- | --- |
| S-19 | *(Public deployment)* HTTPS only; TLS terminates at the chosen edge. Local development uses plain HTTP on the loopback interface only. |
| S-20 | CORS allow-list limited to the local frontend origins (`http://localhost:5173`, `http://127.0.0.1:5173`) in development, and to the deployed origin(s) later; **no wildcard**; allow only the methods and headers in this specification. |
| S-21 | *(Phase 2)* If the refresh token is a cookie: `HttpOnly; Secure`, narrow `Path`, appropriate `SameSite`, and a CSRF review. |
| S-22 | Send `X-Content-Type-Options: nosniff`; enforce a request-size limit. |

### 19.6 Data protection and privacy

| ID | Requirement |
| --- | --- |
| S-23 | *(Public deployment)* CVs and answers are personal data. Cloud storage buckets are private with server-side encryption and public access blocked; the database is encrypted at rest and reachable only from the application. |
| S-24 | Never log CV text, answers, tokens or passwords; log IDs, sizes, durations and error codes. |
| S-25 | *(Only if GenAI is added)* Minimise what is sent to an external LLM (strip contact details, send only needed text) and review the provider's retention and training terms (OD-10). |
| S-26 | *(Public deployment)* Users can delete a CV (E10) already in the MVP; a full account/data deletion path and retention periods are required before real users are onboarded (OD-10, Section 22). |
| S-27 | Error responses never expose internals (stack traces, SQL, file paths, library messages). |

### 19.7 Operational security (later phase)

| ID | Requirement |
| --- | --- |
| S-28 | *(Deployment)* Structured logging with `request_id` to the platform's log service; alarms on error rate and latency. |
| S-29 | *(Deployment)* The database sits in a private network position reachable only from the application; administrative access is restricted. |
| S-30 | *(Deployment)* If a gateway forwards to a publicly reachable application address, the backend must verify a shared origin-secret header so the API cannot be reached by bypassing the gateway (Section 20). |

### 19.8 Local, single-user demonstration safeguards **[Decided D3, D7]**

| ID | Requirement |
| --- | --- |
| S-31 | **Demo-mode start-up guard.** The application **refuses to start** if `AUTH_MODE=demo` and either `APP_ENV` is not `development` or the configured host is not a loopback address. This enforces "authentication before public deployment" mechanically. |
| S-32 | Bind to `127.0.0.1` only; validate the `Host` header against an allow-list; keep the CORS allow-list from S-20. Do not expose the dev server through a public tunnel while in demo mode. Because multipart uploads are "simple" cross-site requests, **[Recommended]** also require a custom request header (for example `X-AIC-Client`) on state-changing routes, which forces a CORS pre-flight that other websites cannot pass. |
| S-33 | **Private local file storage.** Uploaded CVs live in a dedicated directory that is **never inside the frontend's `public/` or `src/` folders, any static-files mount or any web-served path** (preferably outside the repository altogether, Section 25.5); it is git-ignored; files get random names; the application's own account is the only one with access (restrictive directory permissions on systems that support them); no endpoint serves them. Full-disk encryption on the developer machine is advisable. |
| S-34 | **No private data in version control.** Neither the CV directory, nor `.env`, nor database dumps containing CVs or answers are committed; test fixtures use synthetic CVs only. |

---

## 20. AWS Architecture (later phase)

### 20.1 Status **[Decided D8]**

AWS deployment is a **later phase**. The team's available educational resource is **AWS Academy**, but *which services and credits it provides has not been confirmed*. Therefore:

- **Nothing in the MVP depends on AWS.** The local MVP (Sections 21, 25, 26) is complete without it.
- **No access is assumed** to EC2, RDS, S3 or API Gateway.
- **No resource is created and no cost is incurred** by this document or by the MVP.
- Deployment is attempted only after the local MVP works **and** authentication (Phase 2) is implemented (20.6).

The proposal names EC2, S3, RDS, API Gateway and CloudWatch **[Proposal]**; this section shows where each *would* fit if available, and what to do if it is not.

### 20.2 Questions to confirm first (unresolved — OD-17)

None of these can be answered from the project files. They are listed so the first person with access can check them quickly:

1. Which AWS Academy environment is provided, and is it available to every team member?
2. Which services may actually be created: EC2, RDS, S3, API Gateway, CloudWatch?
3. Are there region restrictions, a spending/credit limit, or limits on instance types and storage?
4. How long does a session last, do running resources stop or get deleted when it ends, and does data persist between sessions?
5. Can a resource be reached from the public internet, and can an IAM role be created for the application?
6. Is it acceptable to place real CVs (personal data) in that environment at all?

### 20.3 Local component → AWS counterpart (only if the services are available)

| Local MVP component | AWS counterpart | Migration step | If the service is unavailable |
| --- | --- | --- | --- |
| FastAPI process on the developer's machine | EC2 instance | install the same application; supply environment variables | demo locally; record the limitation |
| Local PostgreSQL | RDS for PostgreSQL | change `DATABASE_URL`; run the same migrations | run PostgreSQL on the same instance, or stay local |
| Private local CV directory | **private** S3 bucket | implement `S3StorageBackend`; set `CV_STORAGE_BACKEND=s3`; copy existing files keeping their keys (Section 25.5) | keep private local storage on the instance |
| Console / file logs | CloudWatch Logs | ship logs and add alarms | keep local logs |
| Browser → FastAPI directly | API Gateway in front of FastAPI | **optional**; not required because the application can serve HTTPS requests behind any reverse proxy | skip it |
| Vite dev server | a static host for the built frontend | build with `npm run build`; hosting choice open (OD-11) | demo locally |
| Demo user, `AUTH_MODE=demo` | **real authentication (mandatory)** | Phase 2 | **do not deploy publicly** |

### 20.4 If API Gateway is used: constraints that shape the design

Verified against the AWS API Gateway quota documentation (October 2026; re-check before use):

| Limit | REST API | HTTP API |
| --- | --- | --- |
| Integration timeout | 29 seconds by default; can be raised, but this may require lowering the account's regional throttle quota | 30 seconds maximum (not adjustable) |
| Payload size | 10 MB (not adjustable) | 10 MB (not adjustable) |

The 5 MB CV limit fits under the 10 MB ceiling. Answer evaluation runs locally and is expected to be well under the timeout, but this is **not yet measured** (OD-13). Type choice (HTTP vs REST) stays open (OD-12).

### 20.5 Possible topologies (options, not decisions)

| Option | Services | Notes |
| --- | --- | --- |
| **Stay local** | none | the committed deliverable if AWS turns out to be unavailable: a reproducible local setup and a README |
| **Single instance** | EC2 only | FastAPI + PostgreSQL + the built frontend on one instance; fewest services and cost; needs real authentication and HTTPS before it is exposed |
| **Managed pieces** | EC2 + RDS + S3 (+ optionally API Gateway, CloudWatch) | closest to the proposal; each piece depends on 20.2 |

Services such as Cognito, CloudFront, Secrets Manager, load balancers, Lambda, queues and any hosted GenAI service are **not assumed** and not needed by this design.

### 20.6 Gate: before any public deployment

All of the following must be true (these are the requirements marked "before public deployment" in Section 19.0):

- Authentication is implemented (Phase 2), `AUTH_MODE` is not `demo`, and E23 is not registered.
- HTTPS is in place and CORS lists only the deployed origin.
- The database is not publicly reachable; secrets are not in the repository.
- CV files are in private storage with no public access.
- A retention and deletion policy for CVs and answers exists (OD-10).
- The cost and session limits from 20.2 are understood.

---

## 21. MVP Scope

Goal: the core workflow end to end — **CV → target role → interview → answers → evaluation → feedback → results → history** — running **locally** with the existing frontend (D1, D6).

### 21.1 Phases

| Phase | Content | Status |
| --- | --- | --- |
| **1 — Local MVP** | the 13 endpoints below, local PostgreSQL, demo user, curated bank, local similarity + rules, private local CV storage | **[Decided]** — the committed scope |
| **1b — Hardening** | the 6 Recommended endpoints (refresh recovery, cleanup, summary) and evaluation validation (V3–V5) | planned, follows Phase 1 |
| **2 — Authentication** | E01–E04, real users, tokens, frontend sign-in | **[Deferred]**; mandatory before public deployment |
| **3 — Cloud deployment** | AWS (or other) hosting, private S3 storage, managed database | **[Deferred]**; depends on AWS Academy availability (OD-17) |
| **4 — Enhancements** | Section 22 | optional |

### 21.2 Included in Phase 1 (local MVP)

| Area | Included |
| --- | --- |
| Endpoints | **13**: the 9 Core (E06, E07, E11, E14, E15, E16, E18, E19, E20) and 4 Supporting (E05 current user, E10 delete CV, E22 health, E23 demo reset) |
| Data | `users` (demo user), `cvs`, `cv_profiles`, `cv_skills`, `interviews`, `interview_questions`, `answers`, `evaluations`, `interview_results`, `user_performance`, `question_bank` — **11 tables** (`refresh_tokens` is Phase 2) |
| CV | upload, validation, text extraction with free libraries, rule-based skills, metadata in PostgreSQL, **private local file storage** |
| Questions | curated bank with reference answers and key points; deterministic selection; CV skill templates |
| Evaluation | local Sentence Transformers (candidate `all-MiniLM-L6-v2`) + explicit rule-based criteria; template feedback; **unvalidated** until Section 16.9 is run |
| Auth | single seeded demo user; safeguards S-31 – S-34 |
| Frontend | the adapter swap behind `api.js` with the mock kept available, plus the changes marked "required for the local MVP" in Section 24.2 (FC-1, 2, 3 (delete), 5, 6, 7, 8, 10, 12, 13) |
| Security | the requirements listed under "Local MVP" in Section 19.0 |

### 21.3 Phase 1b (Recommended endpoints)

E08/E09 (CV list/detail, restores the CV after a refresh), E12 (resume state), E13 (abandon), E17 (fetch evaluation), E21 (dashboard summary) — **6 endpoints** — and the human-rated validation (V3–V5). They improve robustness but the first demo works without them.

### 21.4 Explicitly **not** in the MVP

Authentication and real user accounts · any AWS resource, S3 or API Gateway · GenAI question/ideal-answer/feedback generation (OpenAI, Bedrock or anything paid) · BERT/DistilBERT scoring heads and model fine-tuning · Whisper / speech answers · dynamic follow-up questions · job-description input · RAG with generation, and scraped job-posting pipelines · asynchronous job processing · account deletion and data export · email verification and password reset · antivirus scanning · multi-language support · admin tools for the question bank.

### 21.5 Definition of done for Phase 1

1. All nine `api.js` functions work against the real backend with the mock switched off, and the mock still works when switched on.
2. Flows A–E (Section 3.3) pass manually from the browser.
3. A brand-new database (no interviews) shows the dashboard and performance pages without crashing (F26).
4. Frontend-submitted scores have no effect (S-03), verified by a test.
5. Smoke and property checks V1–V2 pass; V3–V5 are either done and reported or the UI says plainly that scores are unvalidated estimates.
6. The UI no longer claims to measure "confidence" (FC-13).
7. A README lets someone else run the backend locally from scratch; no private data or secrets are committed (S-34).

---

## 22. Future Enhancements

Everything here is **outside** the local MVP. "Depends on" says what must happen first.

| Enhancement | Notes / sketch | Depends on |
| --- | --- | --- |
| **Authentication (Phase 2)** | E01–E04, `refresh_tokens`, frontend sign-in (FC-4), `AUTH_MODE=jwt`, E23 removed | mandatory before any public deployment (D3) |
| **AWS deployment (Phase 3)** | Section 20 options; private S3 storage; managed database | OD-17, Phase 2 |
| **Private S3 storage** | `S3StorageBackend` behind the existing storage interface; migrate files keeping their keys (Section 25.5) | OD-17 |
| **Optional GenAI** | `question_source` / `feedback_source` gain `genai`; provider-agnostic adapter with rules as fallback; privacy and prompt-injection work (Section 16.5) | a decision to add it, provider choice, budget |
| **BERT / DistilBERT scoring** | replace or complement the criteria with a fine-tuned model behind the same scorer interface | labelled data from the human-rated set (Section 16.9) |
| **Speech answers (Whisper)** | add `POST /api/v1/transcriptions` (multipart audio) returning `{ "text": "…" }`; the user confirms, then E15 stores it with `input_mode: "speech"`; needs a recorder in the UI and a larger machine | D6 revisited |
| **Dynamic follow-up questions** | `POST /interviews/{id}/questions/{qid}/follow-up`; the UI's fixed `n` and progress bar would need to change | F21, GenAI |
| **Job-description input** | optional `job_description` on E11, stored with the interview, used for selection | OD-7 |
| **RAG with generation; job-posting data** | offline ingestion of postings/resources, retrieval, generation | GenAI; OD-14 |
| **Async processing** | `202 Accepted` + `GET /jobs/{id}` | only if local evaluation proves too slow (OD-13) |
| **Account and data deletion** | `DELETE /users/me`; replaces the demo-only reset in a real deployment | Phase 2, OD-10 |
| **Delete a past interview** | `DELETE /interviews/{id}` | — |
| **Email verification, password reset** | | Phase 2 |
| **Antivirus scanning, direct-to-S3 uploads** | S-11 | Phase 3 |
| **Server-side strengths/improvement lists** | return them from the server instead of ranking client-side | — |
| **Admin tooling for the question bank** | edit/import bank content without redeploying | OD-14 |

---

## 23. Open Decisions / Questions

The team is inactive, so every item still open carries a **default to proceed with**. A default is a working assumption, not a decision; it can be overturned later without redoing the MVP.

### 23.1 Items from v0.1 and how the working decisions resolved them

| ID | Question (v0.1) | Resolution | What remains |
| --- | --- | --- | --- |
| OD-1 | Authentication method | **Resolved for the MVP by D3**: deferred; single demo user; auth-ready architecture | Phase 2 sub-questions only: refresh token in cookie vs body; whether changing email needs verification (non-blocking) |
| OD-2 | PostgreSQL or MySQL | **Resolved by D2**: PostgreSQL locally; SQLite only as a documented temporary fallback | Whether RDS is available → OD-17 |
| OD-3 | GenAI provider and whether GenAI is in the first release | **Resolved by D4**: no GenAI, no paid API | nothing for the MVP; provider choice is a future decision (Section 22) |
| OD-4 | How structured CV information is extracted | **Resolved in principle by D4/D7**: rule-based extraction with free libraries | the skills list → OD-15 |
| OD-5 | Question source and role of RAG | **Resolved in principle by D4**: curated bank; retrieval only, no generation | the bank's content → OD-14 |
| OD-6 | Speech input (Whisper) in the first release | **Resolved by D6**: deferred | — |
| OD-7 | Job-description input | **Not decided explicitly.** D6's workflow list does not include it, so it is treated as *not in the MVP* | still open as a future question; non-blocking |
| OD-8 | Exact scoring and "confidence score" | **Partly resolved by D5**: similarity + explicit criteria; no claim about psychological confidence; scoring only on the backend | constants, weights, thresholds, calibration data and the acceptance threshold are **unresolved** (see 23.2) |
| OD-9 | Profile edge cases | **Resolved for demo mode**: email editable without verification; "Reset demo data" → E23 | Phase 2: real account semantics |
| OD-10 | Retention, consent, provider data handling | **Partly resolved**: the MVP is local and sends nothing to any provider | retention, consent and deletion policy for a **public** deployment remain open |
| OD-11 | Where the React build is hosted | **Deferred with AWS (D8)** | open until Phase 3 |
| OD-12 | API Gateway type and EC2 reachability | **Deferred with AWS (D8)**; API Gateway is optional | open until Phase 3 |
| OD-13 | Latency budgets and sync vs async | **Partly resolved**: locally there is no gateway limit and no external call | actual evaluation time on the team's machines is **not measured** |

### 23.2 Still open (new or remaining)

Ordered by how much they block.

#### OD-14 — Question bank content (blocks E11 end to end)
- **Question:** who writes the questions, reference answers and key points; how many; for which roles; under what licence?
- **Why unresolved:** the proposal mentions "curated interview question banks" as a data source but names none, and gives no size or authorship.
- **Derived minimum:** Section 8.3 (at least 15 entries per type-and-difficulty cell, a general fallback set, role-specific entries for the 7 preset roles).
- **Default to proceed:** the team authors an initial bank itself (so licensing is simple), starting with the general set, and a script checks the minimums before the server accepts the bank.

#### OD-8 (residual) — Scoring constants and acceptance (blocks trustworthy scores, not coding)
- **Question:** similarity-to-score mapping bounds, thresholds, band limits, category weights, and what correlation with human ratings counts as acceptable.
- **Why unresolved:** no data exists yet; fixing numbers now would be invention.
- **Default to proceed:** implement the configurable structure of Section 16.4 with placeholder constants, mark `scoring_version` as draft, run Section 16.9, and set the acceptance threshold *before* the human-rating step.

#### OD-15 — Source of the skills list used for CV skill extraction
- **Question:** which curated list of skills the rule-based extractor matches against.
- **Default to proceed:** a plain file maintained by the team, seeded from the bank's `skill_tags` plus common technology terms, so the bank and the CV vocabulary agree.

#### OD-16 — DEPI programme requirements
- **Question:** do the programme's rules require authentication, cloud deployment, a particular deliverable format or demo, or forbid anything this plan does?
- **Why unresolved:** only the team's proposal was available; the programme's own requirements were not.
- **Default to proceed:** the proposal is the only specification; deferring authentication does not conflict with it; the deliverable is a working local demo. Check the programme rubric as soon as it is reachable.

#### OD-17 — AWS Academy availability
- **Question:** the six questions in Section 20.2.
- **Default to proceed:** assume nothing is available; Phase 3 stays optional.

#### OD-18 — Keep the original CV file after text extraction?
- **Question:** D7 says to store CV metadata and extracted information in PostgreSQL and to keep files out of public locations; it does not say whether the original file must be kept at all. The frontend never downloads it.
- **Default to proceed:** keep the file privately (allows re-parsing when the extractor improves), controlled by `RETAIN_ORIGINAL_CV` (default `true`); setting it to `false` stores only the extracted text — less personal data kept.

#### OD-19 — The team's development machines
- **Question:** operating systems, Python version, free disk and memory, and whether PostgreSQL and PyTorch can be installed. D5 itself says "if compatible with the development machine".
- **Default to proceed:** Python 3.12; run the one-line compatibility check (Section 26, step 8) before building on the model; if it fails, record the blocker and use `SIMILARITY_BACKEND=lexical`; if PostgreSQL cannot run, record the blocker and use SQLite (D2).

#### Smaller items (non-blocking)
- OD-7 job descriptions (future).
- OD-10 retention policy for a public deployment (before Phase 3).
- OD-11 and OD-12 hosting and gateway choices (Phase 3).
- OD-13 measured evaluation latency (measure during Section 26, step 9).
- Phase 2 sub-questions of OD-1.

### 23.3 Recommendations in this document that the team may override

| Recommendation | Section |
| --- | --- |
| `/api/v1` base path, `snake_case`, lowercase enums, UUID ids | 4.1 |
| No `success` wrapper; uniform `error` envelope | 4.1, 18 |
| Evaluation as `POST` (idempotent) plus `GET` | 10 |
| `PUT` answer (upsert) | 9 |
| Reference answers copied into each interview at creation and hidden until evaluated | 8 |
| E23 (demo reset) as a development-only endpoint | 4.5 |
| Category **Structure** replacing **Confidence** | 16.4, FC-13 |
| The specific criteria, signals and chunking in 16.4 | 16.4 |
| `user_performance` as a recomputed table | 15.2 |
| In-process model loading; explicit lexical fallback | 16.6 |
| Python 3.12 and the dependency list | 25.2 |
| Backend folder placed inside the existing project root as `backend/` | 25.1 |

---

## 24. Frontend Integration Plan

### 24.1 Principles **[Decided D1]**

1. **Preserve the existing React/Vite frontend and its functionality. Do not overwrite or recreate it.** Nothing in this task changes it.
2. **Keep the `api` object and its function names.** Components and contexts keep calling `api.uploadCV()`, `api.startInterview()`, and so on.
3. **Do the translation inside `api.js`** (an adapter) using the mapping in Section 17.3, so UI code keeps its current data shapes.
4. **Keep the mock implementation available** behind a switch (for example `VITE_USE_MOCK_API`) until the backend is stable, so the app keeps working at every step.
5. The backend lives in a **new `backend/` folder** next to `src/` (Section 25.1); no frontend file is moved.

### 24.2 Required frontend changes

"Phase" says when each is needed. The four issues you asked to be carried forward are **FC-1** (missing CV id), **FC-2** (stable question ids), **FC-13/S-03** (server-side scoring), and **FC-7** (empty-history dashboard).

| ID | Change | Where (today) | Phase | Finding |
| --- | --- | --- | --- | --- |
| **FC-1** | **Pass the CV id when starting an interview** — e.g. `startInterview(config, cvId)` using `cvFile.id` | `InterviewSetup.jsx` → `InterviewContext.start` → `api.startInterview` | local MVP | F1 |
| **FC-2** | **Keep `question.id` in the session** and call `submitAnswer(sessionId, question.id, answer)` instead of passing the array index | `InterviewContext.jsx` | local MVP | F2 |
| **FC-3** | Call `deleteCV` from "Remove"/"Replace"; *(1b)* on app start call `listCVs` to restore the CV after a refresh | `useCVUpload.js`, `AppContext.jsx` | delete: local MVP · restore: 1b | F9 |
| FC-4 | Authentication: sign-in/registration screens, token handling, `Authorization` header, silent refresh, sign-out calling E04, user from `GET /users/me` | `Landing.jsx`, `Navbar.jsx`, `AppContext.jsx`, new pages | **Phase 2** (not needed for the local MVP) | F10 |
| **FC-5** | Format `completed_at` into the existing display string in the adapter | `api.js` | local MVP | F5 |
| **FC-6** | Throw a typed `ApiError { status, code, message, retryable }`; show `message`; client-side timeout (401 handling is Phase 2) | `api.js`, screens' catch blocks | local MVP | F13 |
| **FC-7** | **Empty states:** guard `rankSkills`, and render Dashboard and Performance for a user with no completed interviews | `utils/scoring.js`, `Dashboard.jsx`, `Performance.jsx` | local MVP | F26 |
| **FC-8** | Use `XMLHttpRequest` (or equivalent) so `onProgress` reports real upload progress | `api.js` | local MVP | F14 |
| FC-9 | Call `abandonInterview(id)` when the user confirms "Exit" | `InterviewProgress.jsx` | 1b | F12 |
| **FC-10** | Wire "Reset demo data" to E23 (and hide the button when the backend is not in demo mode). Note the behaviour change: history is empty afterwards (F11, F26) | `Profile.jsx` | local MVP | F11 |
| FC-11 | Read dashboard stats and the trend from E21 instead of computing them from the full history | `Dashboard.jsx`, `Performance.jsx` | 1b | F6 |
| **FC-12** | Read the API base URL from `import.meta.env.VITE_API_BASE_URL` and append `/api/v1` | `api.js` | local MVP | — |
| **FC-13** | **Replace "Confidence" with "Structure" and the overall "confidence" wording with "score"**, because psychological confidence is not measured (D5). Exact places found by search: `utils/scoring.js` (`mean('Confidence')`, the `Communication` formula), `pages/Dashboard.jsx` ("Average confidence", "average confidence score"), `data/constants.js` (landing text "See your confidence and skills improve…"). The mock (`data/mockData.js`, `services/mockEngine.js`) must be renamed in step so mock and real data keep the same shape. **The adapter must not map `structure` back to the label "Confidence".** | listed files | local MVP | F16 |
| FC-14 | Make wording truthful to the MVP: "Questions generated from your own experience…" → questions *selected from a curated bank and tailored to your CV and role*; "AI recommendations/insight" → automated feedback; add a visible note on the Evaluation and Results pages that scores are **automated estimates for practice** (Section 16.8) | `data/constants.js`, `Results.jsx`, `Performance.jsx`, `Evaluation.jsx` | recommended with the MVP | F27 |

Required for the local MVP: FC-1, 2, 3 (delete), 5, 6, 7, 8, 10, 12, 13. Phase 1b: FC-3 (restore), 9, 11. Phase 2: FC-4. FC-14 is recommended for honesty.

### 24.3 Target behaviour of each `api.js` function

| Function | New behaviour |
| --- | --- |
| `uploadCV(file, onProgress)` | multipart `POST /cvs` with progress events → `{ id, name }` |
| `startInterview(config, cvId)` | `POST /interviews`; map enums; return `{ id, questions:[{id, text, type}], config }` |
| `submitAnswer(sessionId, questionId, answer)` | `PUT …/answer` → `{ ok: true }` |
| `getEvaluation(sessionId, question)` | `POST …/evaluation` → UI `ev` shape (with `Structure`) |
| `completeInterview({ session })` | `POST …/complete` → UI results shape (client `items` are no longer sent) |
| `getInterviewResults(meta)` | `GET /interviews/{meta.id}/results` → UI results shape |
| `getInterviewHistory()` | `GET /interviews?status=completed&limit=100` → array of UI `meta` (may be empty) |
| `getSkills()` | `GET /performance/skills` → object preserving order (may be empty) |
| `updateProfile(profile)` | `PATCH /users/me` → `{ id, name, email }` |
| *new:* `deleteCV`, `resetDemo` | E10, E23 (Phase 1) |
| *new, later:* `getMe`, `listCVs`, `abandonInterview`, `getSummary`; Phase 2: `register`, `login`, `logout` | thin wrappers around E05, E08, E13, E21; E01, E02, E04 |

### 24.4 Implementation order

The single implementation sequence — backend steps and the frontend swap interleaved — is in **Section 26**.

### 24.5 Contract verification

- Generate the OpenAPI document from FastAPI and diff it against Sections 4–14.
- Use the JSON examples in this document as test fixtures (the adapter tests should turn each API example into the UI shape shown in Section 17.3).
- Keep one end-to-end check per Flow A–E (Section 3.3).

---

## 25. Local Development: Structure, Dependencies and Environment

**Specification only — nothing in this section has been installed, created or run.** Versions were read from PyPI metadata on October 19, 2026 and will move; they are a reference, not pins.

### 25.1 Proposed backend layout

The backend is **new** and sits in a `backend/` folder **inside the existing project root**, next to the untouched frontend (`src/`, `public/`, `package.json`). No frontend file is moved, so the frontend is neither overwritten nor recreated (D1).

```
ai-interview-coach/                 ← existing project root (frontend unchanged)
├── API_SPECIFICATION.md
├── src/  public/  package.json …   ← existing Vite frontend
└── backend/                        ← NEW
    ├── README.md                   how to run (kept short and accurate)
    ├── requirements.txt            runtime dependencies (25.2)
    ├── requirements-dev.txt        test/lint tools
    ├── .env.example                variable names, no real values (25.3)
    ├── alembic.ini  migrations/    schema migrations (Section 15)
    ├── app/
    │   ├── main.py                 creates the app: CORS, routers, start-up checks
    │   ├── config.py               settings from environment + the S-31 demo-mode guard
    │   ├── db.py                   engine and session
    │   ├── deps.py                 get_db, get_current_user (demo user today)
    │   ├── errors.py               error envelope and handlers (Section 18)
    │   ├── models/                 SQLAlchemy tables (Section 15)
    │   ├── schemas/                request/response models (Section 17)
    │   ├── api/                    routers: health, users, cvs, interviews, answers,
    │   │                           evaluations, results, performance, demo
    │   ├── services/               interview lifecycle, question selection, aggregation
    │   ├── cv/                     validation, text extraction, skill rules
    │   ├── scoring/                similarity (sbert | lexical), criteria, scorer, templates, config
    │   ├── storage/                base.py, local.py (s3.py later)
    │   └── data/                   question_bank.json, skills list, feedback templates
    ├── scripts/                    seed_bank.py, check_model.py
    ├── storage/                    PRIVATE CV files — created at run time, git-ignored
    └── tests/                      pytest
```

`backend/.venv/`, `backend/.env`, `backend/storage/` and any database dumps are added to `.gitignore` (S-34).

### 25.2 Python dependencies

All packages below are free and open source; **none is paid** and none requires an account or API key. Install **incrementally**, only when the step that needs them is reached (Section 26) — in particular, the model library is large and should not be installed first.

**Python version.** Use **Python 3.12**. Reason: SQLAlchemy 2.1 and pydantic-settings 2.16 require Python ≥ 3.11 and NumPy 2.5 (installed with the model library) requires ≥ 3.12; every other package below supports ≥ 3.10.

| Package | Purpose | Needed from step | Checked on PyPI | Licence |
| --- | --- | --- | --- | --- |
| `fastapi` | web framework | 1 | 0.149.0 | MIT |
| `uvicorn` | server that runs FastAPI | 1 | 0.54.0 | BSD-3 |
| `pydantic` | validation (installed with FastAPI) | 1 | 2.14.1 | MIT |
| `pydantic-settings` | read settings from environment / `.env` | 1 | 2.16.0 | MIT |
| `sqlalchemy` | database access (ORM) | 2 | 2.1.5 | MIT |
| `alembic` | schema migrations | 2 | 1.20.0 | MIT |
| `psycopg[binary]` | PostgreSQL driver (the `binary` extra avoids needing a C compiler; connection URL scheme `postgresql+psycopg://`) | 2 | 3.3.6 | LGPL-3.0 |
| `python-multipart` | required by FastAPI for file uploads | 4 | 0.0.32 | Apache-2.0 |
| `pypdf` | PDF text extraction (pure Python) | 4 | 6.21.1 | BSD-3 |
| `python-docx` | DOCX text extraction | 4 | 1.2.0 | MIT |
| `sentence-transformers` | local embedding model; pulls in PyTorch, `transformers` and NumPy | 8 | 6.1.0 | Apache-2.0 |
| `pytest` *(dev)* | tests | 1 | 9.1.1 | MIT |
| `httpx` *(dev)* | lets tests call the API in-process | 1 | 0.28.1 | BSD-3 |
| `ruff` *(dev, optional)* | linter/formatter | any | 0.17.1 | MIT |

**Deliberately not used.** `python-dotenv` (`pydantic-settings` already reads `.env`); `scikit-learn` (not needed — the lexical fallback uses only the standard library); `PyMuPDF` for PDFs (dual-licensed **AGPL** or commercial, which could create licence obligations — `pypdf` is permissive); `pdfminer.six` (MIT; a reasonable alternative if `pypdf` extracts poorly from a particular layout); any OpenAI/Bedrock/AWS SDK (`boto3`) — not needed until Phase 3 or GenAI.

**Version policy.** After the first successful install, record the exact versions that worked (for example with `pip freeze`) and keep them in `requirements.txt`. Several releases above are only days old at the time of writing (FastAPI's was published the same day); if a brand-new release causes trouble, use the previous one. **Frontend:** no new npm dependency is required (`XMLHttpRequest` is built in).

### 25.3 Environment variables

Read once at start-up through one settings class (`config.py`). Names are suggestions. `backend/.env.example` lists them **without real values**; the real `.env` is git-ignored (S-16).

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `development` | `development` or `production`; `AUTH_MODE=demo` is refused unless this is `development` (S-31) |
| `AUTH_MODE` | `demo` | `demo` (single seeded user) now; `jwt` in Phase 2 |
| `HOST` | `127.0.0.1` | address to bind; must be loopback in demo mode (S-31) |
| `PORT` | `8000` | port |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | accepted `Host` header values (S-32) |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | allowed browser origins (S-20) |
| `DATABASE_URL` | *(required)* | e.g. `postgresql+psycopg://interview_user:<password>@localhost:5432/interview_coach`; `sqlite:///./dev.db` only for the documented fallback |
| `DEMO_USER_NAME` / `DEMO_USER_EMAIL` | `Alex Morgan` / `alex.morgan@email.com` | the seeded demo user (matches the frontend's `DEMO_USER`) |
| `CV_STORAGE_BACKEND` | `local` | `local` now, `s3` later |
| `CV_STORAGE_DIR` | `./storage/cvs` | private directory for CV files; an absolute path **outside the repository** is preferable (S-33) |
| `MAX_CV_BYTES` | `5242880` | upload ceiling (5 MB) |
| `CV_MIN_TEXT_CHARS` | *(set at implementation)* | minimum extracted text below which `CV_UNREADABLE` is returned — value not chosen here |
| `RETAIN_ORIGINAL_CV` | `true` | keep the original file after extraction (OD-18) |
| `QUESTION_SOURCE` | `bank` | `bank` only in the MVP |
| `QUESTION_BANK_PATH` | `app/data/question_bank.json` | seed file for `question_bank` |
| `SKILLS_LIST_PATH` | `app/data/skills.txt` | skills vocabulary for CV skill extraction (OD-15) |
| `SIMILARITY_BACKEND` | `sbert` | `sbert` (local model) or `lexical` (explicit fallback, Section 16.6) |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | model id (candidate, D5) |
| `EMBEDDING_MODEL_PATH` | *(empty)* | local folder with the model files, for offline use |
| `SCORING_CONFIG_PATH` | `app/scoring/config.json` | the versioned constants, weights and thresholds (Section 16.4) |
| `EVALUATION_TIMEOUT_SECONDS` | *(set after measuring)* | budget for E16; value not chosen here (OD-13) |
| `LOG_LEVEL` | `INFO` | logging verbosity (never logs CV text or answers, S-24) |
| *Phase 2* `JWT_SECRET`, `ACCESS_TOKEN_MINUTES`, `REFRESH_TOKEN_DAYS` | — | only when `AUTH_MODE=jwt` |
| *Phase 3* `S3_BUCKET`, `AWS_REGION` | — | only when `CV_STORAGE_BACKEND=s3` |

**Frontend variables** (a local `.env` file next to `package.json`, git-ignored): `VITE_API_BASE_URL` (the backend origin without a path, for example `http://127.0.0.1:8000`; the adapter appends `/api/v1`) and `VITE_USE_MOCK_API` (`true` keeps the mock, `false` uses the backend). The existing `.env.example` shows `http://localhost:8000`; use `127.0.0.1` locally if `localhost` resolves to IPv6 on your machine — both origins are in the CORS allow-list.

### 25.4 Local database setup (documentation — not executed)

**Primary: PostgreSQL on the developer's machine (D2), free.**

1. Install PostgreSQL with the official installer for your operating system, **or** run it in a container — either is free. If using a container, publish the port **only on the loopback address** (`127.0.0.1:5432`).
2. Create a role and an empty database, choosing your own password:
   ```sql
   CREATE USER interview_user WITH PASSWORD '<choose-a-password>';
   CREATE DATABASE interview_coach OWNER interview_user;
   ```
3. Put the connection URL in `backend/.env` as `DATABASE_URL` (never commit it).
4. Create the tables only through migrations (`alembic upgrade head`), never by hand.

**Fallback: SQLite — only if step 1 is a blocker.** Write down what blocked PostgreSQL, set `DATABASE_URL=sqlite:///./dev.db`, enable foreign-key enforcement for each connection, and run migrations in batch mode. Limits are in Section 15; anything verified only on SQLite is not considered verified. This does **not** change the primary decision.

**Moving to AWS RDS later (if permitted):** change `DATABASE_URL`, run the same migrations. No application code changes if the portability rules in Section 15 were followed.

### 25.5 Private local CV storage and the path to private S3 **[Decided D7]**

| Rule | Detail |
| --- | --- |
| Location | `CV_STORAGE_DIR` — default `backend/storage/cvs`, git-ignored; an absolute path **outside the repository** is preferable. It must **never** be inside the frontend's `public/` or `src/`, a static-files mount, or any web-served folder |
| Names | each file is saved as `<random-uuid>.<ext>`; the original filename is kept only as metadata in the database |
| Database | stores a **relative** `storage_key` and `storage_backend = local` |
| Path safety | every resolved path is checked to lie inside the storage directory (no `..` tricks); user input is never used to build a path |
| Access | no endpoint serves the file; FastAPI never mounts the directory as static files; restrictive directory permissions where the OS supports them |
| Lifecycle | the file is removed by E10 and E23; if the database write fails, the file is removed |
| Minimising data | with `RETAIN_ORIGINAL_CV=false` only the extracted text is kept (OD-18) |

**Future migration to private S3 (Phase 3, only if available — OD-17):**

1. Add an `S3StorageBackend` with the same three operations as the local one (save, open, delete); nothing else in the application changes.
2. Create a **private** bucket with *Block Public Access* on and server-side encryption; the application authenticates with an IAM role rather than keys stored in files.
3. Set `CV_STORAGE_BACKEND=s3`, `S3_BUCKET`, `AWS_REGION`.
4. Copy each existing local file to the bucket **keeping its key**, update that row's `storage_backend` to `s3`, verify, then delete the local copy.
5. No pre-signed URLs are needed: the browser never downloads a CV.

### 25.6 Planned run commands (documentation — not executed)

```
# backend (from the backend/ folder)
python -m venv .venv                    # then activate it
pip install -r requirements.txt
alembic upgrade head                    # create the tables
python scripts/seed_bank.py             # load the question bank
uvicorn app.main:app --host 127.0.0.1 --port 8000

# frontend (project root, unchanged)
npm run dev                             # http://localhost:5173
```

---

## 26. Implementation Sequence (beginner-friendly)

A plan for building a **locally runnable** FastAPI backend in small steps, each of which ends with something you can *see working* before moving on. Nothing here has been done yet.

**Working rules for every step**

1. Do **one step at a time**; do not start the next until the check passes.
2. **Install packages only when a step says so** (Section 25.2); the model library comes late on purpose.
3. **Commit after each working step** — and never commit `.env`, CV files, database dumps or real personal data (S-34).
4. Add a test for each endpoint as you build it; a green test run is part of "done".
5. If something is blocked, **write the blocker down** and use the documented fallback instead of silently changing a decision (D2, D5).
6. The frontend keeps working at every step because the mock stays available (Section 24.1).

### Before step 1 (no code needed; can run in parallel)

- Confirm Python 3.12 is installed, and note each teammate's operating system, free disk space and memory (OD-19).
- Start writing the **question bank** entries (OD-14, Section 8.3): this is the longest non-coding task and it blocks step 6.

### The steps

| # | Goal | What you build | Install | Check that it works | Frontend |
| --- | --- | --- | --- | --- | --- |
| **1** | **Skeleton that starts** | `backend/` folder, virtual environment, `app/main.py`, `config.py` (settings + the demo-mode start-up guard S-31), the error envelope, request ids, CORS, and a minimal **`GET /api/v1/health`** (E22, without database checks yet) | `fastapi`, `uvicorn`, `pydantic-settings`; dev: `pytest`, `httpx` | server starts; `http://127.0.0.1:8000/api/v1/health` returns JSON; `/docs` opens; starting with `APP_ENV=production` and `AUTH_MODE=demo` **refuses to start**; the tests pass | none |
| **2** | **A database that migrates** | PostgreSQL created (25.4), `db.py`, Alembic, first migration for `users`, seeding of the demo user, database check added to E22 | `sqlalchemy`, `alembic`, `psycopg[binary]` | `alembic upgrade head` succeeds; the demo user row exists; health shows `database: ok` | none |
| **3** | **First real endpoints** | `get_current_user` (demo), **E05** `GET /users/me`, **E06** `PATCH /users/me` | — | tests; in `/docs` the name changes and persists after a restart | **first swap:** add the adapter foundation (FC-12 base URL, FC-6 typed errors, the `VITE_USE_MOCK_API` switch) and move **Profile** to the backend — proves the whole chain early |
| **4** | **CV upload** | storage backend (25.5), file validation (S-06 – S-10), text extraction, rule-based skills, tables `cvs`, `cv_profiles`, `cv_skills`, **E07** and **E10** | `python-multipart`, `pypdf`, `python-docx` | tests with small **synthetic** PDF/DOCX files: wrong type → 415, over 5 MB → 413, valid file → 201 with skills; the stored file sits in the private directory under a random name and is gone after delete | swap `uploadCV` and the Remove button (FC-8 real progress, FC-3 delete) |
| **5** | **A usable question bank** | `question_bank` table, `seed_bank.py`, and a **checker script** that fails if any (type × difficulty) cell has fewer than 15 entries or a reference answer is too long (Section 8.3) | — | the checker passes on your seed file | none |
| **6** | **Create an interview** | `interviews` and `interview_questions` tables; **E11** with the selection rules (Section 7) and `QUESTION_BANK_INSUFFICIENT` | — | tests: exactly *n* distinct questions, requested type respected, CV-template questions filled from the CV, unknown CV → 404, impossible request → 422 | swap `startInterview` — **FC-1** (send the CV id) and **FC-2** (keep question ids) |
| **7** | **Store answers** | `answers` table, **E15** with the 30–1500 rules | — | tests: short → `ANSWER_TOO_SHORT`, resubmit replaces, answering after evaluation is refused | swap `submitAnswer` (question id) |
| **8** | **Can this machine run the model?** | `scripts/check_model.py`, then the similarity engine with chunking (16.4) behind the `sbert`/`lexical` switch; reference embeddings cached | `sentence-transformers` | the script encodes two sentences and prints a cosine similarity. **If it cannot run, write down why and use `SIMILARITY_BACKEND=lexical`** (16.6) | none |
| **9** | **Evaluate an answer** | criteria signals, scoring constants file (draft `scoring_version`), feedback templates, `evaluations` table, **E16**; **V1–V2 checks** (16.9); **measure** how long an evaluation takes (OD-13) | — | tests: reference answer scores high, unrelated text low, same input twice gives the same result, a 1500-character answer works, **a score sent by the client changes nothing** (S-03) | swap `getEvaluation` — the UI now shows **Structure** (**FC-13**, adapter and mock renamed together) |
| **10** | **Finish, results, history, skills** | `interview_results`, `user_performance`; **E14**, **E18**, **E19**, **E20**; empty-state responses | — | tests: incomplete → 409, results match the formulas in Section 11, a brand-new user gets empty lists, numbers round half up | swap the remaining functions; **FC-5** dates; **FC-7** empty-state fixes so Dashboard/Performance do not crash |
| **11** | **Demo reset and the rest of Phase 1b** | **E23** (development only), then E08, E09, E12, E13, E17, E21 as time allows | — | after reset the app shows its empty state; E23 returns 404 outside demo/development | **FC-10**; later FC-3 restore, FC-9, FC-11 |
| **12** | **Full walk-through** | nothing new — switch the mock **off** and run Flows A–E (Section 3.3) in the browser | — | every flow works; refresh and error cases behave | all required FCs done |
| **13** | **Check the evaluation honestly** | human-rated sample set, calibration on one subset and reporting on another, written report (16.9 V3–V5) | — | a report exists and the UI/README claims match it; if the result is weak, say so and adjust the wording (FC-14) | FC-14 notes |
| **14** | **Wrap up Phase 1** | README for `backend/`, `.env.example`, the checklist in Section 21.5 | — | someone else can run it from scratch | — |

After step 14: **Phase 2** (authentication) if a public deployment is wanted, then **Phase 3** (AWS) only if OD-17 allows.

### The exact first implementation task

> **Step 1 — create the backend skeleton and the health endpoint.**
> In a new `backend/` folder, create a Python 3.12 virtual environment; install only `fastapi`, `uvicorn`, `pydantic-settings`, `pytest` and `httpx`; write the settings loader with the `AUTH_MODE` / `APP_ENV` / `HOST` start-up guard; implement the uniform error envelope and request ids; and implement `GET /api/v1/health` returning `{"status": "ok", ...}`.
> **Done when:** the server starts on `127.0.0.1:8000`, the health URL returns JSON, `/docs` loads, the server **refuses to start** with `APP_ENV=production` and `AUTH_MODE=demo`, and `pytest` passes.
> It touches no database, no model and no frontend file.

---

## Appendix A — Validation report

This appendix records the checks made before the specification was called complete. "Verified mechanically" means a script compared this document with the source code or with itself; everything else was checked by reading. **No backend exists, so nothing here has been tested against running code, and the AI evaluation has not been validated.**

### A.1 Every frontend service function against the API

| Function | Endpoint | What the UI sends today → what the API needs | What the UI consumes | Result |
| --- | --- | --- | --- | --- |
| `uploadCV(file, onProgress)` | E07 | file → file | `res.id` only | Supported. Real progress needs XHR (FC-8) |
| `startInterview(config)` | E11 | `{role,type,diff,n}` → **plus `cv_id`** *(issue 1)* | `id`, `questions[].text/type` (**plus stable `id`** *(issue 2)*) | Supported **after FC-1, FC-2** |
| `submitAnswer(sessionId, index, answer)` | E15 | index → **question id** *(issue 2)* | nothing | Supported **after FC-2** |
| `getEvaluation(sessionId, question, answer)` | E16 | question text + answer → **question id only** | `score, cats, strengths, weaknesses, tip, ideal` | Supported **after FC-2**; the category `Confidence` becomes `Structure` (FC-13) |
| `completeInterview({session, config, items})` | E14 | client `items` and scores → **nothing** *(issue 3: server-side scoring, S-03)* | `meta, items[{q,ev}], extraStrength, extraImprovement, recommendations` | Supported; the client payload is ignored |
| `getInterviewResults(meta)` | E18 | `meta` → `meta.id` | same results shape | Supported via adapter |
| `getInterviewHistory()` | E19 | — | `id, date, role, type, diff, n, score, status` | Supported via adapter; may be **empty** *(issue 4)*; 100-row cap (F6) |
| `getSkills()` | E20 | — | ordered skills object | Supported via adapter; may be **empty** — **breaks the UI until FC-7** *(issue 4)* |
| `updateProfile(profile)` | E06 | `{name,email}` → `{name?,email?}` | returned user | Supported (demo user) |

The four issues carried forward from the earlier analysis are: **(1)** missing CV id (F1, FC-1) · **(2)** stable question ids (F2, FC-2) · **(3)** server-side scoring only (F4, S-03, Section 16.4) · **(4)** empty-history dashboard (F26, FC-7).

### A.2 Frontend operations → endpoint

| Frontend operation | Endpoint(s) | Note |
| --- | --- | --- |
| Upload / replace CV | E07 (+ E10 for replace) | |
| Remove CV | E10 | no function today (F9) |
| Restore CV after refresh | E08 / E09 | Phase 1b |
| Choose role / type / difficulty / count; type or clear an answer; next question; theme toggle; history filter; estimated time | none — client-only | filter may use E19's optional `type` |
| Start interview | E11 | |
| Submit answer | E15 | |
| View evaluation, expand "stronger answer example" | E16 (the example is in the same response) | |
| Finish interview | E14 | |
| Exit interview | E13 | Phase 1b (F12) |
| Open results (dashboard, history) / per-question modal | E18 / none (data already in the payload) | |
| Dashboard and Performance figures | E19 + E20 (E21 recommended) | must handle empty data (F26) |
| Save profile | E06 | |
| Load current user | E05 | |
| Sign in / sign out | none in the MVP (navigation only, as today) | E01–E04 deferred (D3) |
| Reset demo data | E23 | development only; history is empty afterwards (F11) |

### A.3 Do the database models support every operation?

| Operation | Reads | Writes |
| --- | --- | --- |
| Upload CV | — | `cvs`, `cv_profiles`, `cv_skills`, private file |
| Delete CV | `cvs` | `cvs`, `cv_profiles`, `cv_skills`, `interviews.cv_id` → NULL, file |
| Create interview | `cvs`, `cv_skills`, `question_bank` | `interviews`, `interview_questions` |
| Submit answer | `interviews`, `interview_questions` | `answers` |
| Evaluate | `answers`, `interview_questions` (reference answer, key points) | `evaluations` |
| Complete | `evaluations`, `answers`, `interview_questions` | `interview_results`, `interviews`, `user_performance` |
| Results | `interview_results`, `interviews`, `interview_questions`, `answers`, `evaluations` | — |
| History | `interviews` | — |
| Skills / summary | `user_performance`, `interviews` | — |
| Profile | `users` | `users` |
| Demo reset | `cvs`, `interviews` | deletes from the tables above except `users`, `question_bank` |

Every field the UI displays is stored: `meta` fields in `interviews`; evaluation fields in `evaluations` (+ reference answer in `interview_questions`); results strings in `interview_results`; skills in `user_performance`.

### A.4 Alignment with the proposal

The full proposal-to-MVP table is Section 1.7. Summary of how the finalized decisions relate to the proposal:

- **Kept as proposed:** CV upload and text conversion, target role, text answers, FastAPI, relational storage, Sentence Transformers semantic similarity, strengths/weaknesses/suggestions, history and performance tracking, the human-rated-benchmark correlation as acceptance test (not yet run).
- **Kept in reduced form:** personalized questions (selected from a bank, not generated), RAG (retrieval only), the "confidence score" (an overall answer score).
- **Deferred:** BERT/DistilBERT, GenAI, Whisper, follow-up questions, job descriptions, AWS.
- **Deliberate deviation from the proposal's wording:** the proposal speaks of a "confidence score"; D5 forbids claiming to measure psychological confidence from text, so the per-answer category is **Structure** and the overall figure a *score*. This is the one place the specification departs from the proposal's terminology.
- **Additions not in the proposal**, tagged **[Recommended]**: the demo user and E23, the error envelope and API conventions, the specific scoring criteria, `user_performance`, abandon/resume endpoints.

### A.5 Frontend items that cannot be supported as the UI stands today

| Item | Why | Resolution |
| --- | --- | --- |
| Starting an interview | UI never sends the CV id (F1) | FC-1 |
| Answer/evaluation calls | UI addresses questions by index/text (F2) | FC-2 |
| Scoring | the old `completeInterview` sent client-built scores (F4) | backend ignores them (S-03) |
| New users with no history | `rankSkills({})` throws (F26) — verified by running the function | FC-7 |
| "Confidence" labels | psychological confidence is not measured (F16) | FC-13 |
| Truthful wording | "generated", "AI recommendations" (F27) | FC-14 |
| Real upload progress | `fetch` has none (F14) | FC-8 |
| CV removal / restore | no API call; state in memory (F9) | FC-3 |
| "Reset demo data" | sample history is no longer restored (F11) | FC-10 |
| Authenticated access | no login UI (F10) | **not needed for the local MVP**; FC-4 in Phase 2 |
| Exit cleanup, resume | no API call (F12) | FC-9 (Phase 1b) |
| Dynamic follow-ups, speech, job description | fixed `n`, text-only UI, no field (F21–F23) | deferred |
| Full-history assumptions | stats computed from a complete list (F6) | E21 / FC-11, or the 100-row cap |

### A.6 Requirements that remain unresolved

See Section 23.2: **OD-14** question-bank content, **OD-8** scoring constants and acceptance threshold, **OD-15** skills list, **OD-16** DEPI programme requirements, **OD-17** AWS Academy availability, **OD-18** keeping the original CV file, **OD-19** team machines — plus the small items listed there. Each has a default so work can proceed.

Provisional values to confirm: maximum role length 100, name length 2–100, minimum CV text length (not set), evaluation timeout (not set), mixed-interview ratio, all scoring constants. Unstated assumption: **interviews are in English**.

### A.7 Totals

| Item | Count |
| --- | --- |
| API endpoints | **23** (9 Core · 4 Supporting · 4 Deferred authentication · 6 Recommended); **13 in the first local MVP** |
| Frontend service functions analysed | 9 (all mapped) |
| Frontend findings | 27 (F1–F27) |
| Frontend changes | 14 (FC-1…FC-14); 10 required for the local MVP |
| Database tables | 12 specified; **11 in the MVP** (`refresh_tokens` is Phase 2) |
| Error codes | 33 |
| Security requirements | 34 (S-01…S-34) |
| Finalized decisions | 8 (D1–D8) |
| Open items | 19 identifiers (OD-1…OD-19); 13 from v0.1 resolved, partly resolved or deferred by the decisions, 6 new (OD-14…OD-19) plus the residuals listed in 23.2 |

### A.8 How this was validated, and its limits

**Verified mechanically** (a script run against the repository and this file): the nine `api.js` functions are all mapped; the endpoint catalog has 23 unique IDs, each with a detail section whose method and path match; classes total 9/4/4/6; every `F`, `FC`, `S`, `OD`, `D` and `E` reference resolves; every error code used in the text exists in the catalog; every in-document link resolves; all JSON examples parse; example numbers are consistent (history average = summary average, Communication = rounded mean of Clarity and Structure, skills sorted, question counts match); every `S` requirement is assigned to a phase in Section 19.0; the term "confidence" appears only where the specification explains its removal or limits; the UI limits quoted (5 MB, PDF/DOCX, answer 30–1500, role ≥ 3) and findings F1, F4, F5, F7, F26 match the actual source; the frontend files are unchanged by this task; dependency versions and licences were read from PyPI; the model's 256-word-piece truncation was checked against its published model information.

**Not verified, because nothing exists yet to test:** that the backend works; that the chosen model suits this content; that the scoring criteria correlate with human judgement (Section 16.9 has not been run); latency on the team's machines; AWS Academy availability. **Everything in this document is specification, not implementation, and no claim of AI accuracy is made.**
