# AI Interview Coach

A web app for practising job interviews. Candidates create an account, upload a CV, pick a target role, answer interview questions selected for their skills and role, and get scored, coach-style feedback with a history of their progress.

DEPI capstone project, Team 147. **Status: Milestone 3**, a full-stack local MVP:

- React + Vite frontend
- FastAPI backend
- PostgreSQL database with Alembic migrations
- real accounts and per-user data isolation
- automated answer evaluation

| Document | Contents |
| --- | --- |
| `README.md` (this file) | overview, quick start for the whole project, manual test checklist |
| `backend/README.md` | backend setup, configuration, migrations, tests, API, security, troubleshooting |
| `API_SPECIFICATION.md` | the API and data design the implementation follows |
| `.env.example`, `backend/.env.example` | every setting, with placeholders only |

## Tech stack

- **Frontend:** React 18, Vite 5, React Router 6, Framer Motion, plain CSS with design tokens (light/dark)
- **Backend:** Python 3.12+ (developed on 3.13), FastAPI, SQLAlchemy 2, Alembic, PostgreSQL (psycopg 3), PyJWT, pypdf
- **Evaluation:** curated question bank plus explainable rule-based scoring; optional local Sentence-Transformers model. No paid or external AI service.

## How the pieces connect

```text
Browser ── http://localhost:5173 ──► Vite dev server ── /api/* proxied ──► FastAPI :8000 ──► PostgreSQL :5432
          (React app, same origin)                                        (JWT + HttpOnly refresh cookie)
```

All data access in the frontend goes through `src/services/api.js`. It adds the access token, refreshes the session silently, converts API responses into the shapes the UI components use, and turns errors into readable messages.

## Quick start (Windows PowerShell)

Prerequisites: Node.js 18+, Python 3.12+, PostgreSQL running locally with the `interview_coach` database and user (see `backend/README.md` section 3).

**Terminal 1: backend**

```powershell
cd "path\to\grad project\backend"
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
# first time: add JWT_SECRET (and check DATABASE_URL) in backend\.env, see backend\.env.example
alembic upgrade head
python scripts/seed_question_bank.py
uvicorn app.main:app --reload
```

**Terminal 2: frontend**

```powershell
cd "path\to\grad project"
npm install
npm run dev
```

Open **http://localhost:5173**, then click **Sign up**.

Other frontend commands: `npm run build` (production build in `dist/`) and `npm run preview`. A production deployment must serve the API on the same site as the frontend (or set `VITE_API_BASE_URL` and the backend's `CORS_ORIGINS`) over HTTPS.

## AI features and what powers them (Milestone 5)

Everything works offline with no AI keys: questions are retrieved from the curated bank, answers are scored with transparent rubric rules, and adaptive follow-ups are chosen by a rule-based agent. Two optional upgrades are configured only in `backend/.env`:

- `SIMILARITY_BACKEND=sbert`: a local embedding model for semantic matching (`pip install -r backend/requirements-ml.txt`).
- `LLM_PROVIDER=openai_compatible`: an LLM proposes follow-ups and reviews evaluations, always checked by the app's rules. Off by default; a local server such as Ollama keeps data on your machine; hosted providers additionally need `LLM_ALLOW_EXTERNAL=true` (see backend README 9b).

The interview setup screen shows which mode is active, and every follow-up says whether it was rule-based or proposed by a model.

## Routes

| Path | Screen | Access |
| --- | --- | --- |
| `/` | Landing | public |
| `/signup`, `/login` | Create account / log in | public (signed-in users are redirected to the dashboard) |
| `/dashboard` | Dashboard | signed in |
| `/cv-upload` | CV upload (PDF/DOCX, max 5 MB) | signed in |
| `/interview/setup` | Role, type, difficulty, question count, optional job description, adaptive follow-ups | signed in |
| `/interview/session`, `/interview/evaluation` | Answer a question / feedback | signed in, active interview |
| `/results` | Interview results | signed in |
| `/history`, `/performance`, `/profile` | History, trends, profile and data deletion | signed in |
| `/profile/review` | Review and confirm the profile extracted from your CV | signed in |
| `/plan`, `/plan/:interviewId` | Improvement plan (latest / for one interview) | signed in |

Opening a private page while signed out goes to `/login` and returns to that page after logging in.

## Project structure

```text
src/
├── components/   reusable UI, incl. RouteGuards (RequireAuth, RedirectIfAuthenticated)
├── context/      AuthContext (session), AppContext (user data), InterviewContext, Theme, Toast
├── hooks/        useAuth, useApp, useInterview, useCVUpload, ...
├── pages/        one component per route, incl. AuthPage (login + sign-up)
├── services/     api.js: the only module that calls the backend
├── data/         constants.js (UI options and copy)
├── styles/       design tokens and global styles
└── utils/        scoring display helpers, formatting, navigation
backend/          FastAPI app, migrations, tests (see backend/README.md)
```

## Manual end-to-end checklist (two accounts)

With both servers running:

1. Open http://localhost:5173. You see **Log in** and **Sign up**, and no "Sign in as Alex".
2. Open http://localhost:5173/dashboard directly. You are sent to the login page.
3. **Sign up** as user A. Try a mismatched password confirmation first to see the validation message. You land on A's dashboard with an empty state.
4. Press **F5**. You are still signed in.
5. Upload a PDF or DOCX CV. Reload the page; the CV is still shown.
6. Start a 5-question interview, answer every question (at least 30 characters each), view each evaluation (categories: Relevance, Clarity, Technical Depth, Structure), then **Finish & view results**.
7. Check **History**, **Dashboard** and **Performance**. They show this interview and its scores.
8. Profile → change your name → Save → reload. The change is kept.
9. Avatar menu → **Log out**. Open `/history`; you are sent to the login page.
10. **Sign up** as user B with another email. B's dashboard, history and CV page are empty.
11. Optional, in the browser DevTools console while signed in as B: request one of A's interview ids, e.g. `fetch('/api/v1/interviews/<A-interview-id>/results')` with B's token. Expect **404**. The automated tests do this for every endpoint.
12. Stop the backend (Ctrl + C) and start it again. Log in as A; the interview and results are still there.
13. Try signing up again with A's email in different letter case. You get "An account with this email already exists."
14. Log in as A with a wrong password. You get "Incorrect email or password."
15. http://127.0.0.1:8000/health and http://127.0.0.1:8000/health/db still answer.

## Accessibility and animation

The app has page transitions, staggered reveals, animated score rings and progress bars, and count-up statistics, all toned down for users who prefer reduced motion. It supports keyboard-operable rows and menus, labelled form controls, a dialog focus trap, a skip link, visible focus states and `aria-live` status messages.
