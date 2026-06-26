"""FastAPI application entrypoint for rag-service.

Phase 0: Only a health endpoint. Later phases add routers, middleware,
and database lifecycle hooks.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from rag_service.config import get_settings

settings = get_settings()

app = FastAPI(
    title="rag-service",
    version="0.1.0",
    description=(
        "Central RAG microservice. Consumed by Level-2-App, Level-3-App, "
        "and future tenants via the X-App-Id header."
    ),
)

# CORS: rag-service is NEVER called from the browser directly. Only
# app backends (Level-2 BE, Level-3 BE, future) talk to it. We keep
# CORS empty by default; if a developer needs to test from a browser
# during local dev, they can set CORS_ORIGINS in .env.
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/api/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Liveness probe. Returns 200 as soon as the process is up."""
    return {
        "status": "ok",
        "service": "rag-service",
        "version": app.version,
    }
