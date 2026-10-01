# AI Interview Coach — Frontend

A React + Vite web app for practising job interviews. Candidates upload a CV, pick a target role, answer tailored questions and receive scored, coach-style feedback.

> **Status:** the frontend is complete and runs entirely on **mock/demo data**. The backend, database, authentication, ML models, GenAI integration and CV parsing are **not implemented yet**; the UI talks to a mock service layer that is ready to be swapped for real API calls.

## Tech stack

- [React 18](https://react.dev) + [Vite 5](https://vitejs.dev)
- [React Router 6](https://reactrouter.com) for routing
- [Framer Motion](https://www.framer.com/motion/) for animation (with `prefers-reduced-motion` support)
- Plain CSS with design tokens (light/dark themes); no UI framework

## Getting started

Requires Node.js 18+.

```bash
npm install
npm run dev       # http://localhost:5173
npm run build     # production build in dist/
npm run preview   # serve the production build
```

When deploying the build to static hosting, configure a fallback to `index.html` so deep links such as `/results` work.

## Routes

| Path | Screen |
| --- | --- |
| `/` | Landing |
| `/dashboard` | Dashboard |
| `/cv-upload` | CV upload (PDF/DOCX, max 5 MB) |
| `/interview/setup` | Role, type, difficulty, question count |
| `/interview/session` | Answer a question |
| `/interview/evaluation` | AI feedback for the answer |
| `/results` | Interview results (after finishing, or opened from history) |
| `/history` | Interview history with filters |
| `/performance` | Score trend and skills |
| `/profile` | Profile and demo reset |

Session, evaluation and results routes are guarded: opening them without the required state redirects to a sensible earlier step.

## Project structure

```
src/
├── animations/    Shared Framer Motion variants
├── components/    Reusable UI (Button, Card, Modal, ProgressBar, ScoreCircle, Navbar, Feedback, ...)
├── context/       Theme, toast, app (user/CV/config/history/results) and interview-session state
├── data/          mockData.js (demo data) and constants.js (UI config and copy)
├── hooks/         useApp, useInterview, useCVUpload, useCountUp, ...
├── pages/         One component per route
├── services/      api.js (service layer) and mockEngine.js (local fake AI)
├── styles/        variables.css (tokens), globals.css, animations.css
├── utils/         scoring, formatting and navigation helpers
├── App.jsx        Providers and routes
└── main.jsx       Entry point
```

State is kept in React context + hooks; no Redux.

## Connecting a backend later

All data access goes through `src/services/api.js` (`api.uploadCV()`, `api.startInterview()`, `api.submitAnswer()`, `api.getEvaluation()`, `api.completeInterview()`, `api.getInterviewResults()`, `api.getInterviewHistory()`, `api.getSkills()`, `api.updateProfile()`).

Each function has a `TODO(backend)` comment where the real HTTP call belongs. Replace the body of a function and keep its return shape; the UI does not need to change. `mockEngine.js` and `data/mockData.js` can be deleted once nothing imports them. `.env.example` lists the planned `VITE_API_BASE_URL`.

## Animation and accessibility notes

- Page transitions, staggered reveals, animated score ring and progress bars, count-up statistics, shared-layout selection highlights, and modal/menu/toast transitions.
- `MotionConfig reducedMotion="user"` plus a CSS media query tone motion down for users who prefer reduced motion.
- Keyboard-operable rows and menus, labelled form controls, dialog focus trap and focus restore, skip link, visible focus states, `aria-live` status messages.
