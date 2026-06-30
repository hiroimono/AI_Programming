"""FastAPI application entrypoint for rag-service.

Phase 0: scaffold with /api/health.
Phase 1: + DB lifespan (Neon ping at startup) + /api/health/live,/ready split.
Later phases: + routers, middleware (X-App-Id, internal JWT), background tasks.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from rag_service.config import get_settings
from rag_service.db import dispose_engine, ping_db

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Run once at startup and once at shutdown.

    Startup: ping the DB so we fail fast if .env is wrong.
    Shutdown: close the connection pool cleanly.
    """
    try:
        await ping_db()
        print("[rag-service] DB ping OK")
    except Exception as exc:  # pylint: disable=broad-except
        # We don't crash here; the app should still serve /api/health/live so
        # the operator can fix .env without losing the process. But /ready
        # will report the failure. Surface ANY error visibly at boot.
        print(f"[rag-service] DB ping FAILED at startup: {exc!r}")

    yield

    await dispose_engine()
    print("[rag-service] DB engine disposed")


app = FastAPI(
    title="rag-service",
    version="0.2.0",
    description=(
        "Central RAG microservice. Consumed by Level-2-App, Level-3-App, "
        "and future tenants via the X-App-Id header."
    ),
    lifespan=lifespan,
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
    """Aggregate health: simple ok if the process is up. Kept for backward
    compatibility; prefer /api/health/live or /api/health/ready."""
    return {
        "status": "ok",
        "service": "rag-service",
        "version": app.version,
    }


@app.get("/api/health/live", tags=["meta"])
async def health_live() -> dict[str, str]:
    """Liveness probe: are we running at all?
    Used by orchestrators to decide whether to restart the container.
    """
    return {
        "status": "alive",
        "service": "rag-service",
        "version": app.version,
    }


@app.get("/api/health/ready", tags=["meta"])
async def health_ready() -> JSONResponse:
    """Readiness probe: can we serve real traffic? Requires DB to be reachable.

    Returns 503 if the DB ping fails so load balancers stop sending traffic
    until the DB is back.
    """
    try:
        db_status = await ping_db()
        body = {"status": "ready", "service": "rag-service", **db_status}
        return JSONResponse(content=body, status_code=status.HTTP_200_OK)
    except Exception as exc:  # pylint: disable=broad-except
        body = {
            "status": "not_ready",
            "service": "rag-service",
            "database": "unreachable",
            "error": str(exc),
        }
        return JSONResponse(
            content=body, status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
