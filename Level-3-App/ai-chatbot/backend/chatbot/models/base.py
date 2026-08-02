"""SQLAlchemy declarative base shared by all chatbot-service models.

Single Base / MetaData; all tables live in the default `public` schema
(this service owns its own database, so no multi-schema juggling like
rag-service needs). Tenant isolation is enforced by a `tenant_id` column
plus PostgreSQL Row-Level Security, not by separate schemas.

Naming convention is enforced so Alembic always generates predictable
index / constraint names across databases.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# PostgreSQL identifier limit is 63 chars; keep names short.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Single declarative base for all chatbot-service models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
