# pylint: disable=no-member,invalid-name
# alembic.op is a runtime proxy; its members (execute, get_bind) are only
# resolvable at execution time, and `revision`/`down_revision` are the
# Alembic-mandated lowercase module names.
"""initial schema + Row-Level Security

Creates all tables (tenants, admin_users, bots, bot_configs, documents,
chunks, conversations, messages, usage_events) exactly as defined on the
models, enables the pgvector + pgcrypto extensions, and applies tenant
isolation RLS policies to the tenant-scoped data tables.

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-02
"""

from __future__ import annotations

from alembic import op
from chatbot.models import RLS_TABLES, Base

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # Extensions must exist before creating VECTOR columns / the HNSW index
    # and before gen_random_uuid() server defaults are used.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # Create every table + index exactly as defined on the models, so future
    # `alembic revision --autogenerate` produces no spurious diffs (DB matches
    # metadata one-to-one).
    Base.metadata.create_all(bind)

    # Row-Level Security on tenant-scoped data tables. FORCE makes the policy
    # apply even to the table owner (the app connects as the owner role on a
    # single-role Neon database, so without FORCE, RLS would be bypassed).
    # The policy denies all rows when app.current_tenant is unset:
    # current_setting(..., true) returns NULL, and `tenant_id = NULL` is never
    # true -> safe default-deny. Table names come from the trusted RLS_TABLES
    # constant (never user input), so the f-strings are injection-safe.
    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {table}
                USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
                WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
            """)


def downgrade() -> None:
    bind = op.get_bind()
    for table in RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    Base.metadata.drop_all(bind)
    # Extensions are intentionally left in place (harmless, possibly shared).
