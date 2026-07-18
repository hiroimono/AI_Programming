# syntax=docker/dockerfile:1.7
# ─── RAG-Service production image ─────────────────────────────────
# Python 3.12-slim base: small footprint, official, and pinned so
# rebuilds are deterministic. We never use `python:3.12` (rolling)
# in production — would surprise us with point-release changes.

FROM python:3.12-slim AS base

# Prevent Python from buffering stdout/stderr — Railway log stream
# needs immediate flushes to surface uvicorn / alembic output live.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install OS-level dependencies. We only need libpq for asyncpg's
# health (asyncpg ships its own driver; libpq is not strictly
# required but keeps psql tooling available for ad-hoc debug).
# `--no-install-recommends` keeps the image lean.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Create an unprivileged user. Running uvicorn as root is a textbook
# OWASP A05 (Security Misconfiguration) violation; even inside a
# container, drop privileges.
RUN groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid app --home /app --shell /sbin/nologin app

WORKDIR /app

# ─── Dependency layer ──────────────────────────────────────────────
# Copy ONLY requirements.txt first so Docker can cache the pip layer
# across code changes. Bumping a Python file should not reinstall
# 50+ packages.
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# ─── App layer ─────────────────────────────────────────────────────
# Copy the application code AFTER deps are installed. This is the
# layer that changes most often.
COPY alembic.ini ./
COPY alembic ./alembic
COPY rag_service ./rag_service

# Create the storage root and hand ownership to the unprivileged user.
# Without a Railway volume mount this path is ephemeral (lost on
# redeploy); chunks/vectors live in Postgres so search/chat survive,
# but "download original file" links 404 after a redeploy. Mount a
# volume at /app/storage in Railway to persist originals.
RUN mkdir -p /app/storage \
    && chown -R app:app /app

USER app

# Railway injects PORT at runtime; default to 8100 for local docker
# runs so `docker run -p 8100:8100` mirrors the dev workflow.
ENV PORT=8100 \
    STORAGE_LOCAL_PATH=/app/storage

EXPOSE 8100

# Healthcheck hits the cheapest endpoint that proves the process is
# alive (does NOT touch the DB — that's /api/health/ready). Railway
# also uses this path via railway.toml.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:${PORT}/api/health/live || exit 1

# Entrypoint runs migrations first so a fresh DB or a new revision is
# applied automatically. `exec` replaces the shell so SIGTERM from
# Railway reaches uvicorn directly (clean shutdown, fast deploys).
# Use sh -c so the ${PORT} substitution happens at container start.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn rag_service.main:app --host 0.0.0.0 --port ${PORT}"]
