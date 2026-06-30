# pylint: disable=no-member,unused-argument,wrong-import-position
# alembic.context is a runtime proxy; its members (configure, begin_transaction,
# run_migrations, is_offline_mode, config) are only visible at execution time.
# include_object's full signature is required by Alembic even if we ignore args.
# wrong-import-position is intentional: we bootstrap sys.path before importing
# our rag_service.* modules, which is the standard pattern for alembic env.py.
"""Alembic environment for rag-service.

Custom features beyond the default template:

1. **Async engine**: Uses the same `postgresql+asyncpg://` URL as the app so
   migrations run through asyncpg, no need to maintain a separate sync URL
   (`psycopg2`) just for migrations.

2. **Multi-schema autogenerate**: `include_schemas=True` makes Alembic scan
   every PostgreSQL schema, not just the default `public`. Required because
   our tables live under `rag_level2_writer` and `rag_level3_chatbot`.

3. **Schema isolation guard** (`include_object`): we *only* manage tables
   under the three `rag_*` schemas. This prevents `--autogenerate` from ever
   trying to drop Gateway's tables in `public` just because they're not in
   our metadata. This is THE critical safety net for sharing the DB.

4. **Version table lives in `rag_shared`**: the `alembic_version` bookkeeping
   table is created in `rag_shared` so it doesn't pollute `public` (Gateway's
   schema) and is grouped with our other RAG schemas.

5. **Connection string injection**: reads DATABASE_URL from rag_service.config
   (which loads .env via pydantic-settings). alembic.ini's sqlalchemy.url is
   intentionally blank.

6. **HNSW compare hint** (`compare_type=True`): tells autogenerate to detect
   column type changes — useful when we later change Vector(1536) → Vector(3072)
   or similar dimension migrations.
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
# alembic is invoked as `alembic` from any cwd, so make sure
# `rag_service.*` imports resolve regardless of how we launch it.
ROOT = Path(__file__).resolve().parent.parent  # RAG-Service/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag_service.config import get_settings  # noqa: E402
from rag_service.db import normalize_neon_url  # noqa: E402
from rag_service.models import Base  # noqa: E402  # registers all model tables

# ── Alembic config & logging ────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject DATABASE_URL from .env into Alembic config at runtime, rewriting
# the libpq-style `postgresql://...?sslmode=...` form into the asyncpg
# dialect URL + connect_args that SQLAlchemy expects.
settings = get_settings()
raw_url = settings.database_url.get_secret_value()  # pylint: disable=no-member
if not raw_url:
    raise RuntimeError(
        "DATABASE_URL is empty — set it in RAG-Service/.env before running alembic."
    )
db_url, _connect_args = normalize_neon_url(raw_url)
config.set_main_option("sqlalchemy.url", db_url)

# All four models (Level2Document, Level2Chunk, Level3Document, Level3Chunk)
# are registered against this single MetaData via models/__init__.py imports.
target_metadata = Base.metadata

# Schemas we are allowed to touch. ANYTHING in another schema (e.g. Gateway's
# `public.Users`) is invisible to autogenerate and to apply.
MANAGED_SCHEMAS = {"rag_level2_writer", "rag_level3_chatbot", "rag_shared"}


def include_object(
    obj, name, type_, reflected, compare_to
):  # noqa: ARG001  # pylint: disable=unused-argument
    """Strict whitelist: only manage objects in our 3 RAG schemas.

    CRITICAL safety net. Without this Alembic's autogenerate would propose
    dropping every Gateway table in `public` because they exist in DB but
    not in our metadata. PostgreSQL exposes the default `public` schema as
    `obj.schema = None` on reflected objects, so we MUST treat unknown /
    None schemas as "outside our scope".

    Alembic's include_object hook requires this exact 5-argument signature;
    we ignore everything except the object's schema attribute.
    """
    # Resolve effective schema for tables, indexes, columns, FKs, etc.
    obj_schema = getattr(obj, "schema", None)
    if obj_schema is None and hasattr(obj, "table"):
        obj_schema = obj.table.schema

    # Whitelist only — anything not explicitly in our managed set is OUT.
    # Reflected tables in `public` (Gateway) hit this branch and are dropped
    # from consideration, so autogenerate never proposes destructive ops
    # against them.
    return obj_schema in MANAGED_SCHEMAS


def _do_run_migrations(connection: Connection) -> None:
    """Configure Alembic context against an open DB connection and run."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        include_object=include_object,
        compare_type=True,
        version_table="alembic_version",
        version_table_schema="rag_shared",
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
        # Required when connecting to Neon's pooler endpoint (PgBouncer in
        # transaction mode does not support prepared statements).
        connect_args={"ssl": True, "statement_cache_size": 0},
    )

    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)

    await connectable.dispose()


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of executing it (rarely used; kept for DBA review)."""
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        include_schemas=True,
        include_object=include_object,
        version_table="alembic_version",
        version_table_schema="rag_shared",
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Online mode: open a real connection and run migrations against it."""
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
