"""SQLAlchemy declarative base shared by all RAG schema models.

We keep a SINGLE Base/MetaData and put `__table_args__ = {"schema": ...}` on
each table to assign it to rag_level2_writer / rag_level3_chatbot / rag_shared.
Alembic autogenerate handles multi-schema correctly under one MetaData, and
this is much simpler than juggling three MetaData instances + Alembic
`target_metadata=[m1, m2, m3]` (which has subtle ordering bugs).

Naming convention is enforced so Alembic always generates predictable index/
constraint names (otherwise it produces auto names that drift across DBs).
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
    """Single declarative base for all RAG models across all schemas."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
