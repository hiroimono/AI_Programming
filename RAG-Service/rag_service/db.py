"""Async database engine and session factory.

Why a separate module:
    - The engine is created ONCE at app startup (lifespan), reused for all
      requests. Re-creating per-request is the classic perf-killer.
    - The session factory binds AsyncSession to that engine.
    - All other modules (routers, RAG pipeline) import session_factory from
      here; nobody else touches engine internals.

Neon-specific notes:
    - Connection string starts with `postgresql://` (libpq-style). We rewrite
      it to `postgresql+asyncpg://` so SQLAlchemy picks the async driver.
    - Neon enforces SSL. libpq uses `?sslmode=require` in the URL; asyncpg
      doesn't recognize that query param. We strip it and pass `ssl=True`
      via connect_args instead.
    - Neon idles compute when no connections are held. Pool pre-ping avoids
      "connection lost" errors after a cold start.
"""

from __future__ import annotations

from typing import AsyncIterator
from urllib.parse import urlparse, urlunparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from rag_service.config import get_settings


def _normalize_neon_url(raw_url: str) -> tuple[str, dict]:
    """Convert a libpq-style Neon URL to asyncpg-compatible form.

    Returns:
        (clean_url_without_query, connect_args_for_asyncpg)
    """
    if not raw_url:
        raise RuntimeError(
            "DATABASE_URL is empty. Set it in RAG-Service/.env. "
            "Format: postgresql://user:pwd@host/dbname?sslmode=require"
        )

    # Swap the dialect prefix so SQLAlchemy uses the async driver.
    if raw_url.startswith("postgresql://"):
        raw_url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif raw_url.startswith("postgres://"):
        # Some hosts emit `postgres://` (deprecated alias); normalize too.
        raw_url = raw_url.replace("postgres://", "postgresql+asyncpg://", 1)

    parsed = urlparse(raw_url)
    # asyncpg rejects unknown query params like sslmode/channel_binding.
    cleaned = urlunparse(parsed._replace(query=""))

    # Neon enforces TLS; tell asyncpg to use it.
    # statement_cache_size=0 is REQUIRED when connecting via Neon's
    # `-pooler` endpoint (PgBouncer in transaction mode), which does not
    # support prepared statements. Safe to keep enabled for direct
    # endpoints too — costs a tiny bit of perf but avoids surprise crashes
    # if someone swaps the URL later.
    return cleaned, {"ssl": True, "statement_cache_size": 0}


def _build_engine() -> AsyncEngine:
    """Create the singleton AsyncEngine from settings."""
    settings = get_settings()
    # pylint mis-infers pydantic v2 Field() defaults as FieldInfo; suppress it.
    raw = settings.database_url.get_secret_value()  # pylint: disable=no-member
    url, connect_args = _normalize_neon_url(raw)

    return create_async_engine(
        url,
        echo=False,  # Set True for raw SQL debug logs in development.
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,  # Avoid "stale connection" after Neon cold-start.
        connect_args=connect_args,
    )


# Module-level singletons created on first import. App lifespan should call
# `dispose_engine()` on shutdown.
engine: AsyncEngine = _build_engine()

session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def ping_db() -> dict[str, str]:
    """Run `SELECT 1` to confirm the DB is reachable. Used by /health/ready."""
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1 AS ok"))
        row = result.first()
    return {
        "database": "ok" if row is not None and row.ok == 1 else "unexpected",
    }


async def dispose_engine() -> None:
    """Close all pooled connections. Call on app shutdown."""
    await engine.dispose()


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yields a request-scoped AsyncSession.

    Usage:
        @router.get(...)
        async def handler(db: AsyncSession = Depends(get_session)):
            ...
    """
    async with session_factory() as session:
        yield session
