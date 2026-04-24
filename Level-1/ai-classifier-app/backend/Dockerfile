# Dockerfile — FastAPI Backend Container
# ========================================
# Multi-stage build: first install dependencies, then copy app code.
# This keeps the final image small and speeds up rebuilds.
#
# .NET comparison:
#   Like a Dockerfile for a .NET WebAPI project,
#   but using Python + uvicorn instead of dotnet + Kestrel.

# --- Stage 1: Base image with Python ---
FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered output
# (so logs appear immediately in Railway/Docker logs)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# --- Stage 2: Install dependencies ---
FROM base AS dependencies

# Copy only requirements first (Docker caches this layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Stage 3: Final image ---
FROM dependencies AS final

# Copy application code
COPY . .

# Create directories that the app needs at runtime
RUN mkdir -p output prompts

# Railway automatically sets the PORT environment variable
# Default to 8000 if not set
ENV PORT=8000

# Expose the port (documentation for Docker, Railway reads PORT env)
EXPOSE ${PORT}

# Start the FastAPI server
# --host 0.0.0.0 = accept connections from outside the container
# --port $PORT   = use the port Railway assigns
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
