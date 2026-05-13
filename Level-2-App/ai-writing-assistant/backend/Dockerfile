# Dockerfile — AI Writing Assistant Backend
# ==========================================
# Multi-stage build for FastAPI + SSE streaming.

# --- Stage 1: Base image with Python ---
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# --- Stage 2: Install dependencies ---
FROM base AS dependencies

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Stage 3: Final image ---
FROM dependencies AS final

COPY . .

# Railway sets PORT env var automatically
ENV PORT=8001

EXPOSE ${PORT}

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
