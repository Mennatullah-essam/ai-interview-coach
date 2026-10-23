# AI Interview Coach — Backend

Python + FastAPI + PostgreSQL backend for AI Interview Coach.

**Status: Milestone 3.** Real user accounts (sign up, log in, log out, session persistence), per-user data isolation, CV upload and parsing, interviews from a curated question bank, automated answer evaluation, results, history and performance statistics. The React frontend in the project root uses these APIs; there is no mock data or demo user any more.

All commands are for **Windows PowerShell** and run from the **`backend` folder** unless a step says otherwise.

---

## 1. What runs where

| Part | Folder | Command | URL |
| --- | --- | --- | --- |
| Backend (FastAPI) | `backend` | `uvicorn app.main:app --reload` | http://127.0.0.1:8000 (API docs: `/docs`) |
| Frontend (React + Vite) | project root | `npm run dev` | http://localhost:5173 |
| Database (PostgreSQL) | — | Windows service | localhost:5432 |

During development the browser only talks to `http://localhost:5173`. Vite forwards every `/api/...` request to the backend (see `vite.config.js`), so the login cookie is first-party and no CORS setup is needed.

## 2. Folder layout

```text
backend/
├── app/
│   ├── main.py               app factory: middleware, routers, /health, /health/db
│   ├── core/                 config (settings), errors (error envelope), security (passwords, JWT), rate limiting
│   ├── db/                   SQLAlchemy base + engine/session (get_db)
│   ├── models/               ORM tables: users, refresh_tokens, cvs, question_bank, interview_* , answers, evaluations
│   ├── schemas/              request/response models (API spec section 17)
│   ├── api/                  deps (get_current_user), presenters, routes/ (auth, users, cvs, profile, interviews, performance, health)
│   ├── services/             auth, CV parsing, private storage, question bank + selection, interview lifecycle
│   ├── intelligence/         profile extraction, competencies, retrieval, interview agent, improvement plans
│   ├── llm/                  optional LLM gateway + OpenAI-compatible provider (off by default)
│   ├── scoring/              similarity backends (lexical | sbert), criteria scorer, feedback templates, config.json
│   └── data/                 question_bank.json (71 questions), skills.txt, skill_catalog.json, roles.json, resources.json
├── alembic/versions/         migrations: 9c35bf359c62 (initial), 285a552def9d (Milestone 3), d87ec07e6d71 (Milestone 4), ecf75151dd51 (Milestone 5)
├── scripts/                  seed_question_bank.py, set_password.py
├── tests/                    pytest suite (unit, API, isolation, PostgreSQL migration tests)
├── storage/                  PRIVATE uploaded CVs (created at run time, git-ignored)
├── requirements.txt          runtime dependencies
├── requirements-dev.txt      + pytest, httpx2
├── requirements-ml.txt       OPTIONAL local embedding model (large)
└── .env.example              every setting, with placeholders only
```

## 3. Set up (first time, or after pulling Milestone 3)

### 3.1 Python packages

```powershell
cd "path\to\grad project\backend"
py -m venv .venv                       # only if .venv does not exist yet
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt    # installs requirements.txt too
```

If activation says "running scripts is disabled", run once: `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`.

### 3.2 Configure `.env`

You already have a `backend\.env` with `DATABASE_URL` from Milestone 2. **Keep it**, and add the new settings from `.env.example`. At minimum add a real `JWT_SECRET`:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"   # copy the output
code .env                                                        # or: notepad .env
```

```dotenv
DATABASE_URL=postgresql+psycopg://interview_coach_user:<your password>@localhost:5432/interview_coach
JWT_SECRET=<the value you just generated>
```

For a fresh machine: `Copy-Item .env.example .env`, then replace every `CHANGE_ME`. Every variable is explained in `.env.example`. Edit `.env` with VS Code or Notepad, not `echo > .env`; PowerShell 5 would write UTF-16.

### 3.3 Back up, then migrate the database (safe)

Migration `285a552def9d` only **adds** columns and tables. It keeps all existing rows, renames `evaluations.confidence_score` to `structure_score` (values are kept), lower-cases existing emails, and moves the bank's old `role` column into `role_tags`. It was tested on a populated Milestone 2 database (upgrade, downgrade, upgrade). Still, take a backup first:

```powershell
pg_dump -U interview_coach_user -h localhost -d interview_coach -F c -f "$HOME\interview_coach_before_m3.dump"
alembic current          # expect: 9c35bf359c62
alembic upgrade head
alembic current          # expect: 285a552def9d (head)
```

If `pg_dump` is not found, use its full path, for example `& "C:\Program Files\PostgreSQL\18\bin\pg_dump.exe" ...`. To restore, use `pg_restore --clean -U interview_coach_user -h localhost -d interview_coach "$HOME\interview_coach_before_m3.dump"`.

**Existing accounts:** rows created before Milestone 3 have no password, so they cannot log in. Give one a password with `python scripts/set_password.py someone@example.com`, or just register a new account.

### 3.4 Load the question bank

Milestone 5 adds migration `ecf75151dd51` (additive: the `agent_decisions` table and four evaluation columns). Run `alembic upgrade head` and the seed command (it adds misconception patterns to existing questions: `0 created, 71 updated`).

Milestone 4 adds a migration (`d87ec07e6d71`, additive only: two new tables and new columns with safe defaults) and two question-bank entries. After pulling it, back up as in 3.3, then run `alembic upgrade head` and the seed command below. Existing users, CVs, interviews and evaluations are kept; old interviews stay non-adaptive and old evaluations keep their original scores.


```powershell
python scripts/seed_question_bank.py
```

Expected: `Question bank OK: 71 entries` then `Seeded: ...` (on an existing database: `2 created, 69 updated`). It is safe to run again; it updates entries in place. Run it whenever `app/data/question_bank.json` changes.

## 4. Run

```powershell
uvicorn app.main:app --reload
```

| URL | Expected |
| --- | --- |
| http://127.0.0.1:8000/health | `{"status":"healthy","service":"ai-interview-coach-backend"}`. Never touches the database. |
| http://127.0.0.1:8000/health/db | `{"status":"healthy","database":"reachable"}`, or HTTP 503 |
| http://127.0.0.1:8000/api/v1/health | readiness: database, evaluation model, CV storage, question bank |
| http://127.0.0.1:8000/docs | interactive API documentation |

Stop with **Ctrl + C**. Then start the frontend in a second terminal (see the root `README.md`).

## 5. Tests

```powershell
pytest                     # everything
pytest -v                  # one line per test
pytest -m "not postgres"   # skip the PostgreSQL migration tests
```

- **Isolated by design.** API and model tests use an in-memory SQLite database and a temporary CV folder. They never touch `DATABASE_URL`.
- **PostgreSQL migration tests** run only if `TEST_DATABASE_URL` is set. They refuse to run unless its database name ends in `_test` and differs from `DATABASE_URL`, they rebuild that database, and they leave it empty. To enable them, as the `postgres` user: `CREATE DATABASE interview_coach_test OWNER interview_coach_user;`, then add `TEST_DATABASE_URL` to `.env`.

Expected summary: **268 passed** with `TEST_DATABASE_URL`, or **260 passed, 8 skipped** without it. No test needs network access or LLM credentials.

## 6. How authentication works

| Step | What happens |
| --- | --- |
| Sign up / log in | `POST /api/v1/auth/register` or `/login` checks the input, hashes the password with **scrypt** (salted, memory-hard, standard library) and returns a short-lived **access token** (JWT, 15 min) in the JSON body. It also sets a **refresh token** in an `HttpOnly; SameSite=Strict` cookie scoped to `/api/v1/auth` (`Secure` in production). |
| Each API call | The frontend keeps the access token in memory only and sends `Authorization: Bearer <token>`. `get_current_user` validates signature, expiry, issuer and type, then loads the user. No endpoint accepts a user id from the client. |
| Page reload | The in-memory token is gone, so the app calls `POST /api/v1/auth/refresh`. The browser sends the cookie; the server rotates it (old one revoked, new one issued) and returns a new access token. The user stays signed in for up to `REFRESH_TOKEN_DAYS`. |
| Token expiry | A 401 makes the frontend refresh once and retry. If that fails, the user is sent to the login page with "Your session has expired". |
| Log out | `POST /api/v1/auth/logout` revokes the refresh token in the database and clears the cookie. |
| Theft protection | Refresh tokens are stored only as SHA-256 hashes. Re-using an already-rotated token (outside a 20 s grace window for two tabs) revokes **all** of that user's sessions. Refresh and logout also require an `X-AIC-Client` header (CSRF defence). |
| Brute force | Login and sign-up are limited per IP (`AUTH_RATE_LIMIT_PER_MINUTE`, default 10), returning `429 RATE_LIMITED`. Wrong email and wrong password give the same message and timing. |

## 7. API endpoints (all under `/api/v1`)

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/auth/register` | Create account; returns user and access token, sets refresh cookie |
| POST | `/auth/login` | Log in |
| POST | `/auth/refresh` | Restore or extend the session from the cookie (rotates it) |
| POST | `/auth/logout` | End the session |
| GET / PATCH | `/users/me` | Current user / update name or email |
| DELETE | `/users/me/data` | Delete my CVs, profile, interviews and plans (the account stays). This replaces the spec's demo-only reset E23 |
| GET / PUT | `/profile` | My structured candidate profile (built from my newest CV) / save corrections; `confirm: true` makes it personalise interviews |
| POST | `/profile/rebuild` | Re-extract the profile from my newest CV, keeping items I added (back to draft) |
| GET | `/interviews/{id}/improvement-plan` | Improvement plan for one completed interview |
| GET | `/improvement-plans/latest` | Plan for my most recent completed interview |
| POST | `/cvs` | Upload a CV (multipart field `file`, PDF/DOCX, max 5 MB) |
| GET | `/cvs` | My CVs, newest first |
| GET / DELETE | `/cvs/{cv_id}` | One CV with extracted skills / delete it and its file |
| POST | `/interviews` | Create an interview and select its questions. Optional: `job_description` (≤ 5000 chars), `adaptive` (follow-ups) |
| GET | `/interviews` | My completed interviews (history), newest first; `?type=` filter |
| GET | `/interviews/{id}` | Interview state and progress |
| POST | `/interviews/{id}/abandon` | Exit an interview |
| POST | `/interviews/{id}/complete` | Aggregate scores and return results (client scores are ignored) |
| PUT | `/interviews/{id}/questions/{qid}/answer` | Save or replace an answer (30–1500 chars) |
| POST / GET | `/interviews/{id}/questions/{qid}/evaluation` | Evaluate (idempotent) / fetch an evaluation. Adds `dimensions`, `missing_concepts`, `suggestions`, `ideal_outline`, `explanation`, and in adaptive interviews `follow_up` / `replaced_question` |
| GET | `/interviews/{id}/results` | Full results of a completed interview |
| GET | `/performance/skills` | Skill scores across completed interviews |
| GET | `/performance/summary` | Dashboard numbers and score trend |
| GET | `/health` | Readiness check |

Errors always use one envelope: `{"error": {"code", "message", "details", "retryable", "request_id"}}`. Another user's resources return **404**, never 403, so ids cannot be probed.

## 8. Database

```text
users ─┬─< refresh_tokens
       ├─< cvs ──────────────┐ (SET NULL)
       └─< interview_sessions >┘
                 └─< interview_questions >── question_bank (SET NULL)
                           └── answers (0..1) ── evaluations (0..1)
```

| Table | Purpose |
| --- | --- |
| `users` | Account: name, unique lower-cased email, scrypt password hash, active flag |
| `refresh_tokens` | Login sessions (hashed tokens, expiry, revocation) |
| `cvs` | CV metadata, random storage key (never returned), extracted text, skills and profile lines |
| `question_bank` | 71 curated questions (69 + 2 project templates) with reference answers, key points, role/skill tags (shared, not user data) |
| `interview_sessions` | One interview, its status (`in_progress`, `completed`, `abandoned`) and, once completed, its stored result summary |
| `interview_questions` | Questions asked, with a hidden snapshot of the reference answer and key points |
| `answers`, `evaluations` | One answer per question, one evaluation per answer, with scoring provenance and (since Milestone 4) per-dimension scores |
| `candidate_profiles` | Milestone 4: one reviewed profile per user (JSON with provenance per item), `draft` or `confirmed` |
| `improvement_plans` | Milestone 4: one stored plan per completed interview |
| `agent_decisions` | Milestone 5: audit trail of the interview agent (action, rules/llm, policy result, rationale, evidence) |

There are deliberately no separate results or performance tables: results are columns of the completed session, and performance is calculated from them. This differs from the spec's suggested `cv_profiles`, `cv_skills`, `interview_results` and `user_performance` tables, and avoids duplicated data.

To change the schema: edit `app/models/`, then `alembic revision --autogenerate -m "..."`, **read the generated file**, run `alembic upgrade head`, then `pytest`. The test `test_models_and_migrations_are_in_sync` fails if a model change has no migration.

## 9. Answer evaluation — what the scores mean

Scores are **automated estimates for practice**, computed only on the server with documented rules (no external AI service). Since Milestone 4 each answer is scored on six dimensions, each with a one-line explanation:

| Dimension | What it measures |
| --- | --- |
| Relevance | Does the answer address this question? Text similarity is used here only, as supporting evidence. Capped when no expected concept is covered. |
| Key concepts | Which of the question's rubric key points are covered (with synonyms, `app/scoring/concept_synonyms.json`). |
| Technical accuracy | Technical questions only: rubric coverage, minus penalties for known misconceptions (patterns in the question bank) and capped for bare keyword lists. **0 when no concept is covered**, so similar wording alone can't score high. Behavioral answers show "not assessed". |
| Structure | STAR cues (behavioral) or approach/reasoning/example/trade-off cues (technical). |
| Evidence & examples | Concrete examples, numbers, named tools, reasoning. |
| Communication | Length, sentence length, repetition. |

The overall score is a weighted average (weights per question type in `app/scoring/config.json`), and the response explains how it was reached. Each evaluation also returns missing concepts, actionable suggestions, the reference answer and an answer outline (the rubric points). The original four `category_scores` are still returned for compatibility (`clarity` = communication, `technical_depth` = mean of key concepts and technical accuracy).

- `SIMILARITY_BACKEND=lexical` (default) uses term overlap. It runs anywhere and needs nothing extra.
- `SIMILARITY_BACKEND=sbert` uses a local Sentence-Transformers model, `all-MiniLM-L6-v2` (`pip install -r requirements-ml.txt`, a large PyTorch download). The model is loaded once per process. If it can't load, **evaluation** returns `503 AI_SERVICE_UNAVAILABLE` rather than silently mixing scoring methods; **question selection** falls back to lexical ranking.
- Every evaluation stores `scoring_version` (now `lexical-v1` / `sbert-v1`; older ones keep their version) and raw signals. Older evaluations are shown with their original categories.
- **Not validated yet:** constants and weights are hand-chosen. The spec's validation plan (16.9: correlation with human ratings) has not been run, so treat scores as practice guidance.

## 9a. Interview intelligence (Milestone 4)

All rules are deterministic and live outside the routes (`app/intelligence/`, `app/services/question_selection.py`, `app/scoring/`). Reference data: `app/data/skill_catalog.json` (categories and synonyms), `roles.json` (required/preferred skills per role), `resources.json` (official learning links).

1. **Candidate profile** (`profile_extraction.py`): on every CV upload a draft profile is built: technical and soft skills, experience, education, projects, achievements, expertise areas, estimated years, experience level and target role. Every item is tagged `extracted` (with the CV line as evidence), `inferred` (with the rule's reasoning) or `user`. Synonyms are normalised (sklearn → scikit-learn, K8s → Kubernetes). Missing sections and unreadable CVs produce warnings, never invented items. The candidate reviews it at `/profile/review`; only a **confirmed** profile personalises interviews. The server recomputes provenance, so a client can't mark its own additions as "extracted".
2. **Question planning** (`question_selection.py`): questions are ranked by the role's required/preferred skills, skills from the optional job description, and the candidate's skills (plus embedding similarity when sbert is loaded). A balanced plan mixes role-core questions, CV-skill templates, project questions (confirmed profile only), skill-gap checks (required skills missing from the profile) and behavioral questions. No duplicates, a diversity penalty spreads topics, a fixed seed makes it repeatable, and every question carries a `reason`.
3. **Adaptive follow-ups** (`adaptive.py`, opt-in per interview): after a weak technical answer → a clarifying question on the first missing concept; vague answer → a request for a concrete example; strong answer → a deeper trade-off/reflection question. At most one per question, none on a follow-up, and 2 / 3 / 4 per interview (5 / 10 / 15 questions). After two or more answers, the next unanswered question may move one difficulty level (at most twice). Follow-ups are stored with `parent_question_id`. Fixed interviews are unchanged.
4. **Improvement plan** (`improvement.py`): created when an interview is completed. Strengths need an average of 75+; a **gap** needs at least two weak answers (this and earlier interviews); a single weak answer is "needs more evidence"; a required role skill with no evidence is "not yet demonstrated" (not "missing"). Repeated patterns need 2+ answers and 40% of the interview. It also lists practice questions from the bank, official resources, up to five prioritised next steps and progress against the previous plan.

## 9b. Hybrid intelligence (Milestone 5)

Three layers, coordinated through one competency vocabulary (`app/data/competencies.json`, `app/intelligence/competencies.py`):

| Layer | What it does | Where |
| --- | --- | --- |
| Deterministic rules (always on) | rubric evaluation, follow-up policy and limits, duplicate prevention, score bounds, fallbacks | `app/scoring/`, `app/intelligence/agent.py` (`validate`), `question_selection.py` |
| Local embeddings (optional, `SIMILARITY_BACKEND=sbert`) | semantic question retrieval, concept matching in answers | `app/intelligence/retrieval.py`, `app/scoring/concepts.py` |
| LLM (optional, **off by default**) | proposes follow-up decisions; bounded review of an evaluation | `app/llm/`, `agent.propose_llm`, `intelligence/evaluation_review.py` |

**Is an LLM allowed?** The API specification (decision D4, section 16.5) says the MVP uses no paid or external AI service and that no CV text leaves the machine; GenAI is an optional future integration that needs its own review. So the LLM is disabled unless configured, CV text is never sent (only skill names and the answer to one question, with emails, phone numbers and links removed), and a non-local server is refused unless `LLM_ALLOW_EXTERNAL=true`. A free local server (Ollama, LM Studio) keeps everything on your machine. Whether a hosted provider is acceptable is a team decision (proposal owner of "GenAI integration").

**Retrieval** ranks bank questions by role requirements, the job description, the confirmed profile and semantic similarity of a document made of the question, its rubric points and the competency descriptions. It skips near-duplicates of chosen questions (maximal marginal relevance), ranks questions you saw in recent interviews like a one-level difficulty mismatch, and runs a coverage pass so several required skills are assessed, starting with those your interview evidence marks weak or unassessed. Without the model it uses the lexical engine with synonym and alias expansion. Embeddings of bank documents are computed once per model and cached in `storage/embedding_cache/`.

**Interview agent** (adaptive interviews only): after each evaluated answer it decides `continue`, `clarify`, `request_example`, `probe_concept` or `deepen`, using the rubric, the evidence of this answer (missing / incorrect / unsupported), concepts already probed or demonstrated in the interview, follow-ups used, questions left and elapsed time. An LLM may propose the decision; the policy always checks it (adaptive on, budget and time left, no follow-up on a follow-up, no repeated probe, concept must be in the rubric, question must be on topic and must not ask for personal data) and falls back to the rules otherwise. Every decision is stored in `agent_decisions` and returned as `agent_decision`.

**Evaluation** reports, per rubric concept, `demonstrated` / `partial` / `mentioned` (named in a list, not explained) / `missing`, with the sentence from the answer as evidence. Rubric aliases (`app/data/rubric_aliases.json`) recognise other wordings. It separates *incorrect claims* (known misconceptions, lower accuracy) from *missing evidence*, flags *sweeping claims without support*, and reports `evidence_level` (sufficient / limited / insufficient) so a very brief answer is "not shown yet", never a weakness. An optional LLM review can move key concepts and accuracy by at most 15 points, only credits concepts it can quote from the answer, and can never raise accuracy above a detected incorrect claim. Such evaluations have `feedback_source = "hybrid"`.

**Coaching** (`plan-v2`): a question and its follow-up count as one piece of evidence; gaps need two weak answers; brief answers are listed as "not enough evidence"; strengths across two or more interviews are marked consistent; a competency table separates what the profile says from what interviews showed (interviews never change the profile); exercises and resources come only from the curated catalogue.

**Measured on the labelled cases** (`python scripts/benchmark_intelligence.py`, lexical engine, synthetic answers written by the developers, not real-world accuracy):

| | Milestone 4 | Milestone 5 |
| --- | --- | --- |
| Evaluation agreement, development set (73 cases) | 71.2 % | 93.2 % |
| Evaluation agreement, held-out set (25 cases, never used for tuning) | 63.0 % | 70.4 % |
| Correct answers in other words, held-out | 0 / 4 | 0 / 4 |
| Pairwise ordering (strong > partial > wrong …), dev | 42 / 52 | 48 / 52 |
| Unsupported claims flagged | not detected | 8 / 8 dev, 2 / 2 held-out |
| Appropriate follow-up decisions (dev cases) | 87.7 % | 98.6 % |
| Agent fallback when the LLM fails (timeout, invalid output, off-topic) | n/a | 100 % |
| Required-skill coverage per interview (42 planned interviews) | 0.667 | 0.856 |
| Questions repeated in the next interview | 76.4 % | 21.4 % |
| Duplicate questions / deterministic | 0 % / yes | 0 % / yes |
| Median latency: evaluation / planning | 1.9 ms / 2.6 ms | 2.7 ms / 6.8 ms |

The development set was used while writing the aliases and misconception patterns, so its gain overstates real improvement; the held-out gain is the honest number. Paraphrased answers without embeddings remain the main weakness of the lexical fallback; the embedding model is what addresses them, and it could not be downloaded in the environment where this milestone was built, so **its quality, latency and memory were not measured here**. Published facts for `all-MiniLM-L6-v2`: about 22.7 M parameters, 384-dimensional vectors, about 90 MB download, CPU is enough. Measure it on your machine with `SIMILARITY_BACKEND=sbert python scripts/benchmark_intelligence.py` (it prints load time, latency and memory).

## 10. Security notes

- Uploaded CVs: type is checked by content (PDF header, DOCX structure), size by a 5 MB limit enforced before reading, DOCX zip bombs are capped, and encrypted PDFs are rejected. Files are stored under random names in a private folder that is never served.
- Request validation: strict schemas reject unknown fields; a 1 MB limit applies to JSON bodies; responses carry `X-Request-ID` and `X-Content-Type-Options: nosniff`.
- Logs never contain passwords, tokens, CV text or answers (LLM failures are logged by type only).
- LLM: keys only in `backend/.env`, never sent to the browser; replies are schema-validated and policy-checked before anything runs; answers are wrapped as data in prompts (prompt-injection guard).
- `APP_ENV=production` refuses to start without a strong `JWT_SECRET`, with insecure cookies, or with a wildcard CORS origin. Public deployment still needs HTTPS and a retention policy (spec 20.6).

## 11. Troubleshooting

| Problem | Fix |
| --- | --- |
| `DATABASE_URL is not set` | `.env` is missing or not in the `backend` folder |
| `password authentication failed` | wrong password in `DATABASE_URL`, or it needs URL-encoding |
| `/health/db` 503 / connection refused | start PostgreSQL: `Get-Service postgresql*`, then `Start-Service postgresql-x64-18` (as Administrator) |
| `permission denied for schema public` | as `postgres`: `ALTER DATABASE interview_coach OWNER TO interview_coach_user;` |
| `ModuleNotFoundError: jwt / multipart / pypdf` | activate the venv, then `pip install -r requirements-dev.txt` |
| `alembic upgrade` fails on a unique constraint for `users.email` | two accounts differ only by letter case; delete or rename one, then retry |
| Interview creation says "not enough questions" | run `python scripts/seed_question_bank.py` |
| Login works but you are logged out after every reload | open the app via http://localhost:5173 (the Vite proxy), not by calling port 8000 from another origin |
| `429 Too many attempts` | wait one minute (rate limit) |
| Port 8000 in use | stop the other server or use `--port 8001` and set `VITE_API_PROXY_TARGET` |

## 12. Known limitations (later milestones)

- Evaluation scores are unvalidated drafts (see section 9). Rule-based checks can't verify every technical claim; misconception patterns exist for 15 technical questions only.
- Profile extraction is rule-based: unusual CV layouts (tables, two columns, scanned PDFs) can produce incomplete profiles, which is why review is required.
- The plan's resource list covers the skills in `resources.json`; others get a generic practice hint.
- An interview that is in progress cannot yet be resumed after a page reload. The backend supports it (`GET /interviews/{id}`), but the frontend starts a new one instead.
- Rate limiting is in memory: it resets on restart and isn't shared between processes.
- No email verification or password reset. Account deletion keeps the account (data only).
- No GenAI question generation, no speech answers, no AWS deployment (spec D4, D6, D8).
