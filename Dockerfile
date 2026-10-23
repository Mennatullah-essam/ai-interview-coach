# Production image: builds the React frontend, then runs FastAPI, which serves
# both the API (/api/v1/...) and the website from one origin.
#   docker build -t ai-interview-coach .
#   docker run -p 8000:8000 --env-file backend/.env ai-interview-coach
# Configuration comes only from environment variables (never baked into the image).

# --- 1. frontend build ----------------------------------------------------------------
FROM node:20-slim AS frontend
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY index.html vite.config.js ./
COPY public ./public
COPY src ./src
RUN npm run build

# --- 2. backend runtime -------------------------------------------------------------------
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FRONTEND_DIST=/app/dist
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ .
COPY --from=frontend /app/dist /app/dist
RUN useradd --create-home appuser && mkdir -p storage && chown -R appuser /app/backend/storage
USER appuser
EXPOSE 8000
# Migrations are additive and the seed is idempotent, so both are safe on every start.
# PORT is set by hosts such as Render; 8000 otherwise.
CMD ["sh", "-c", "alembic upgrade head && python scripts/seed_question_bank.py && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
