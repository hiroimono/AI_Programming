"""FastAPI application entrypoint for rag-service.

Phase 0: scaffold with /api/health.
Phase 1: + DB lifespan (Neon ping at startup) + /api/health/live,/ready split.
Later phases: + routers, middleware (X-App-Id, internal JWT), background tasks.
"""

from __future__ import annotations

import traceback
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from rag_service.config import get_settings
from rag_service.db import dispose_engine, ping_db
from rag_service.routers import documents_router, retrieve_router

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

# Mount Phase 4 routers. All endpoints under these routers require a
# valid internal JWT (verified by the AuthedIdentity dependency).
app.include_router(documents_router)
app.include_router(retrieve_router)


@app.exception_handler(Exception)
async def _log_unhandled(request: Request, exc: Exception) -> JSONResponse:
    """Print the traceback to stderr so it lands in our log files.
    FastAPI's default handler returns 500 without printing for Exception
    subclasses, which makes debugging through redirected stdio impossible.
    """
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    print(
        f"[rag-service] Unhandled exception on {request.method} {request.url.path}:\n{tb}",
        flush=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"{type(exc).__name__}: {exc}"},
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
