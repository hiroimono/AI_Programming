# pylint: disable=no-member,unused-argument,wrong-import-position
# alembic.context is a runtime proxy; its members are only visible at
# execution time. wrong-import-position is intentional: we bootstrap
# sys.path before importing chatbot.* modules (standard alembic pattern).
"""Alembic environment for chatbot-service.

Simpler than rag-service's env.py: this service owns its own database and
keeps all tables in the default `public` schema, so there is no multi-schema
whitelist to manage.

Custom features beyond the default template:

1. **Async engine**: uses the same `postgresql+asyncpg://` URL as the app,
   so migrations run through asyncpg (no separate psycopg2 sync URL).

2. **Connection string injection**: reads DATABASE_URL from chatbot.config
   (which loads .env via pydantic-settings). alembic.ini's sqlalchemy.url
   is intentionally blank.

3. **compare_type=True**: autogenerate detects column type changes — useful
   for future Vector dimension migrations.
"""

from __future__ import annotations

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ── sys.path bootstrap ──────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent  # backend/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chatbot.config import get_settings  # noqa: E402
from chatbot.db import normalize_neon_url  # noqa: E402
from chatbot.models import Base  # noqa: E402  # registers all model tables

# ── Alembic config & logging ────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
raw_url = settings.database_url.get_secret_value()  # pylint: disable=no-member
if not raw_url:
    raise RuntimeError(
        "DATABASE_URL is empty — set it in backend/.env before running alembic."
    )
db_url, _connect_args = normalize_neon_url(raw_url)
config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata


def _do_run_migrations(connection: Connection) -> None:
    """Configure Alembic context against an open DB connection and run."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    """Build an AsyncEngine and dispatch to the sync runner via run_sync."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"ssl": True, "statement_cache_size": 0},
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of executing it (kept for DBA review)."""
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        compare_type=True,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live async DB connection."""
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
