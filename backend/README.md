# AI Interview Coach — Backend

Python + FastAPI backend for AI Interview Coach.

**Status: Milestone 1 (foundation).** The only endpoint is `GET /health`. There is no database, authentication, CV upload, interview logic or AI integration yet. The frontend still uses its own mock data.

## Frontend and backend are separate servers

During development you run two programs at the same time, in two terminals:

| Part | Folder | Command | URL |
| --- | --- | --- | --- |
| Frontend (React + Vite) | project root | `npm run dev` | http://localhost:5173 |
| Backend (FastAPI) | `backend/` | `uvicorn app.main:app --reload` | http://127.0.0.1:8000 |

They don't start each other. In Milestone 1 the frontend does not call the backend at all.

## Folder layout

```text
backend/
├── app/
│   ├── __init__.py      marks app/ as a Python package
│   └── main.py          FastAPI app and GET /health
├── tests/
│   └── test_health.py   automated tests for /health and /docs
├── .env.example         template for future settings (no variables yet)
├── .gitignore           keeps .venv, caches and .env out of Git
├── pytest.ini           tells pytest where the code and tests are
├── requirements.txt     runtime dependencies (FastAPI, Uvicorn)
├── requirements-dev.txt runtime + test dependencies (pytest, httpx)
└── README.md
```

## Prerequisites

- Python **3.10 or newer** (3.12 or 3.13 recommended).
- Git Bash on Windows.

Check your Python version in Git Bash:

```bash
python --version
# or, if that opens the Microsoft Store or says "not found":
py --version
```

Use whichever command works (`python` or `py`) in the first setup step below. After the virtual environment is activated, `python` always points to the right interpreter.

## First-time setup (Windows, Git Bash)

Run these from the project root (`ai-interview-coach/`):

```bash
cd backend

# 1. Create the virtual environment (only once)
python -m venv .venv          # or: py -m venv .venv

# 2. Activate it (every new terminal)
source .venv/Scripts/activate

# 3. Confirm you are using the venv's Python
which python                  # should end in backend/.venv/Scripts/python

# 4. Upgrade pip and install dependencies (including test tools)
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

When the venv is active your prompt starts with `(.venv)`. To leave it: `deactivate`.

> On Windows the activation script is in `.venv/Scripts/`, not `.venv/bin/` as on macOS/Linux.

## Run the development server

```bash
cd backend
source .venv/Scripts/activate
uvicorn app.main:app --reload
```

`--reload` restarts the server automatically when you save a `.py` file.

Then open:

- Health check: http://127.0.0.1:8000/health
- Interactive API docs (Swagger UI): http://127.0.0.1:8000/docs
- Alternative docs (ReDoc): http://127.0.0.1:8000/redoc

Or check from a second Git Bash terminal:

```bash
curl http://127.0.0.1:8000/health
# {"status":"healthy","service":"ai-interview-coach-backend"}
```

### Stop the server

Press **Ctrl + C** in the terminal running Uvicorn.

## Run the tests

```bash
cd backend
source .venv/Scripts/activate
pytest
```

Expected result (versions and timing will differ):

```text
============================= test session starts =============================
platform win32 -- Python 3.x.x, pytest-x.x.x, ...
rootdir: .../ai-interview-coach/backend
configfile: pytest.ini
testpaths: tests
collected 2 items

tests\test_health.py ..                                                  [100%]

============================== 2 passed in 0.xxs ==============================
```

For more detail use `pytest -v`.

## Configuration

Milestone 1 reads no environment variables. `.env.example` is a placeholder template. When later milestones need settings:

```bash
cp .env.example .env   # then edit .env; never commit it
```

## Troubleshooting

**`python: command not found`, or it opens the Microsoft Store**
Use `py -m venv .venv` instead. If neither works, install Python from python.org and tick "Add python.exe to PATH". You can turn off the Store alias under Windows Settings → Apps → Advanced app settings → App execution aliases.

**`source .venv/Scripts/activate: No such file or directory`**
You are not in `backend/`, or the venv was not created. Run `pwd` and `ls -a` to check.

**`ModuleNotFoundError: No module named 'fastapi'` (or `pytest`)**
The venv is not active or the packages are not installed. Activate it (`source .venv/Scripts/activate`) and run `pip install -r requirements-dev.txt`.

**`ModuleNotFoundError: No module named 'app'` when running Uvicorn or pytest**
Run the commands from inside `backend/`, not the project root.

**`[Errno 10048] ... only one usage of each socket address` / address already in use**
Something is already using port 8000 (often an old Uvicorn window). Stop it with Ctrl + C, or run on another port: `uvicorn app.main:app --reload --port 8001`.

**`pytest` warns about `httpx` vs `httpx2`**
Newer Starlette versions (used by FastAPI) prefer a package called `httpx2` for the test client and print a deprecation warning when they fall back to `httpx`. The tests still run. If you see it, `pip install httpx2` removes the warning; tell your mentor so `requirements-dev.txt` can be updated.

**VS Code uses the wrong interpreter**
Ctrl + Shift + P → "Python: Select Interpreter" → choose `backend\.venv\Scripts\python.exe`.

## What's next (not in Milestone 1)

CORS for the frontend at `http://localhost:5173`, then the endpoints behind `src/services/api.js`. Database, auth, CV parsing and AI evaluation come in later milestones.
