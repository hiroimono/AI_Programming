"""Async database engine, session factory, and RLS tenant helper.

Why a separate module:
    - The engine is created ONCE at app startup and reused for all requests.
    - The session factory binds AsyncSession to that engine.
    - Everyone else (routers, RAG pipeline) imports session_factory / helpers
      from here; nobody touches engine internals.

Row-Level Security (RLS):
    Tenant-scoped data tables have a Postgres RLS policy of the form
        tenant_id = current_setting('app.current_tenant', true)::uuid
    so a query can only ever see/modify the current tenant's rows — even if
    application code forgets a WHERE clause. `set_current_tenant()` sets that
    session variable (a Postgres GUC — Grand Unified Configuration setting)
    right after we authenticate the admin/widget request.
"""

from __future__ import annotations

from typing import AsyncIterator
from urllib.parse import urlparse, urlunparse
from uuid import UUID

from chatbot.config import get_settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def normalize_neon_url(raw_url: str) -> tuple[str, dict]:
    """Convert a libpq-style Neon URL to asyncpg-compatible form.

    Public because alembic/env.py also needs this transformation.

    Returns:
        (clean_url_without_query, connect_args_for_asyncpg)
    """
    if not raw_url:
        raise RuntimeError(
            "DATABASE_URL is empty. Set it in backend/.env. "
            "Format: postgresql://user:pwd@host/dbname?sslmode=require"
        )

    # Swap the dialect prefix so SQLAlchemy uses the async driver.
    if raw_url.startswith("postgresql://"):
        raw_url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif raw_url.startswith("postgres://"):
        raw_url = raw_url.replace("postgres://", "postgresql+asyncpg://", 1)

    parsed = urlparse(raw_url)
    # asyncpg rejects unknown query params like sslmode / channel_binding.
    cleaned = urlunparse(parsed._replace(query=""))

    # Neon enforces TLS. statement_cache_size=0 is REQUIRED when connecting
    # via Neon's `-pooler` endpoint (PgBouncer in transaction mode, which
    # does not support prepared statements).
    return cleaned, {"ssl": True, "statement_cache_size": 0}


def _build_engine() -> AsyncEngine:
    """Create the singleton AsyncEngine from settings."""
    settings = get_settings()
    # pylint mis-infers pydantic v2 Field() defaults as FieldInfo; suppress it.
    raw = settings.database_url.get_secret_value()  # pylint: disable=no-member
    url, connect_args = normalize_neon_url(raw)

    return create_async_engine(
        url,
        echo=False,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,  # Avoid stale connection after Neon cold-start.
        connect_args=connect_args,
    )


# Module-level singletons created on first import. App lifespan calls
# dispose_engine() on shutdown.
engine: AsyncEngine = _build_engine()

session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def set_current_tenant(session: AsyncSession, tenant_id: UUID) -> None:
    """Set the RLS tenant GUC for this session's transaction.

    Uses set_config(..., is_local => true) so the value is scoped to the
    current transaction and cannot leak across pooled connections. The
    tenant id is passed as a bind parameter (never string-interpolated),
    so this is injection-safe.
    """
    await session.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": str(tenant_id)},
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
    """FastAPI dependency: yields a request-scoped AsyncSession."""
    async with session_factory() as session:
        yield session
