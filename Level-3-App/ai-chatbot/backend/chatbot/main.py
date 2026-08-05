"""FastAPI application entrypoint for chatbot-service.

M0: scaffold with /api/health(/live,/ready) + DB lifespan.
Later milestones add routers: auth (M1), bots (M2), documents (M3),
widget sessions (M4), chat SSE (M5).
"""

from __future__ import annotations

import traceback
from contextlib import asynccontextmanager
from typing import AsyncIterator

from chatbot.config import get_settings
from chatbot.db import dispose_engine, ping_db
from chatbot.routers.auth import router as auth_router
from chatbot.routers.bots import router as bots_router
from chatbot.routers.chat import router as chat_router
from chatbot.routers.documents import router as documents_router
from chatbot.routers.widget import router as widget_router
from chatbot.ratelimit import limiter
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Run once at startup and once at shutdown.

    Startup: ping the DB so we fail visibly if .env is wrong.
    Shutdown: close the connection pool cleanly.
    """
    try:
        await ping_db()
        print("[chatbot-service] DB ping OK")
    except Exception as exc:  # pylint: disable=broad-except
        # Do not crash: keep serving /api/health/live so the operator can
        # fix .env without losing the process. /ready reports the failure.
        print(f"[chatbot-service] DB ping FAILED at startup: {exc!r}")

    yield

    await dispose_engine()
    print("[chatbot-service] DB engine disposed")


app = FastAPI(
    title="chatbot-service",
    version="0.1.0",
    description=(
        "Level-3 embeddable AI chatbot backend. Multi-tenant (B2B2C): "
        "tenants manage bots; anonymous end-users chat via the widget."
    ),
    lifespan=lifespan,
)

# Rate limiting: expose the limiter on app.state (slowapi reads it there) and
# map RateLimitExceeded to a 429 response. Registered before the catch-all
# Exception handler so throttled requests return 429, not 500.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS: the admin panel (Angular) and the widget call this API from the
# browser, so their origins must be allow-listed via CORS_ORIGINS in .env.
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.exception_handler(Exception)
async def _log_unhandled(request: Request, exc: Exception) -> JSONResponse:
    """Print the traceback to stderr so it lands in our log files.

    FastAPI's default handler returns 500 without printing for Exception
    subclasses, which makes debugging through redirected stdio impossible.
    """
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    print(
        f"[chatbot-service] Unhandled exception on "
        f"{request.method} {request.url.path}:\n{tb}",
        flush=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"{type(exc).__name__}: {exc}"},
    )


app.include_router(auth_router)
app.include_router(bots_router)
app.include_router(documents_router)
app.include_router(widget_router)
app.include_router(chat_router)


@app.get("/api/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Simple ok if the process is up. Prefer /live or /ready for probes."""
    return {"status": "ok", "service": "chatbot-service", "version": app.version}


@app.get("/api/health/live", tags=["meta"])
async def health_live() -> dict[str, str]:
    """Liveness probe: are we running at all?"""
    return {"status": "alive", "service": "chatbot-service", "version": app.version}


@app.get("/api/health/ready", tags=["meta"])
async def health_ready() -> JSONResponse:
    """Readiness probe: can we serve real traffic? Requires DB reachable."""
    try:
        db_status = await ping_db()
        body = {"status": "ready", "service": "chatbot-service", **db_status}
        return JSONResponse(content=body, status_code=status.HTTP_200_OK)
    except Exception as exc:  # pylint: disable=broad-except
        body = {
            "status": "not_ready",
            "service": "chatbot-service",
            "database": "unreachable",
            "error": str(exc),
        }
        return JSONResponse(
            content=body, status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
