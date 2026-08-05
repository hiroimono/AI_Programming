# syntax=docker/dockerfile:1
# ─────────────────────────────────────────────────────────────────────────────
# Production image for the Level-3 chatbot backend (FastAPI + uvicorn).
#
# PREPARE-ONLY: this Dockerfile is deploy-ready but is NOT built/pushed here.
# The operator builds and deploys it (see docs/DEPLOY-EN.md). Neon PostgreSQL
# is external (managed) — this image contains only the app.
#
# Deploy target: Railway (EU region — Amsterdam — for GDPR). Railway injects
# $PORT; we bind uvicorn to it, defaulting to 8200 for local runs.
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS base

# - PYTHONUNBUFFERED: stream logs immediately (no buffering) for platform log capture.
# - PYTHONDONTWRITEBYTECODE: no .pyc files in the container layer.
# - PIP_NO_CACHE_DIR: smaller image.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8200

WORKDIR /app

# Install dependencies first (own layer) so code changes don't re-run pip.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy only the application package and migration assets (see .dockerignore
# for what is excluded: venv, tests, .env, local storage, caches).
COPY chatbot ./chatbot
COPY alembic ./alembic
COPY alembic.ini ./

# Run as a non-root user (defense-in-depth; container escape hardening).
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/storage \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8200

# Container-level liveness check hitting the app's own probe. Railway also
# has its own healthcheck (railway.json), so this is belt-and-suspenders.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os,urllib.request,sys; \
url=f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8200\")}/api/health/live'; \
sys.exit(0 if urllib.request.urlopen(url, timeout=3).status==200 else 1)"

# Bind to $PORT so the hosting platform can route to us. Single worker: the
# app is async I/O-bound; scale horizontally (more instances) rather than
# with sync workers. NOTE: with >1 instance, move rate-limit storage to Redis
# (see ratelimit.py / docs) — in-memory counters do not share across instances.
CMD ["sh", "-c", "uvicorn chatbot.main:app --host 0.0.0.0 --port ${PORT}"]
