"""Level-2 (AI Writing Assistant) RAG schema: documents + chunks.

Schema: rag_level2_writer

Note: Level-2 and Level-3 schemas are intentionally identical-but-separate
(no shared parent class). This isolation lets us evolve each app's schema
independently without cross-app migration risk, and keeps cross-schema
queries trivially scopable per-tenant.
"""

# pylint: disable=not-callable
# SQLAlchemy's `func` namespace generates attributes dynamically
# (func.now, func.coalesce, ...). Pylint can't see them as callable.

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pgvector.sqlalchemy import Vector
from rag_service.models.base import Base
from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

SCHEMA = "rag_level2_writer"

# OpenAI text-embedding-3-small produces 1536-dim vectors. If you switch to
# text-embedding-3-large (3072 dims) you must write a new Alembic migration
# that ALTERs the column AND rebuilds the HNSW index — vector dim is fixed.
EMBEDDING_DIM = 1536


class Level2Document(Base):
    """Uploaded source file. One row per file the user attaches in chat."""

    __tablename__ = "documents"
    __table_args__ = (
        # Composite index for the common list query: "show me my docs in this
        # conversation". user_id is the hot filter (multi-tenant), so it leads.
        Index(
            "ix_documents_user_conv",
            "user_id",
            "conversation_id",
            "created_at",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    app_id: Mapped[str] = mapped_column(String(50), nullable=False)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    conversation_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )

    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Lifecycle: uploaded -> parsing -> embedding -> ready  (or -> error)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="uploaded")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Backend-storage URI (local path or r2://bucket/key); resolved by storage.py.
    storage_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    # Soft-delete: keep the row so old citations still resolve to a file name.
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    chunks: Mapped[list["Level2Chunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Level2Chunk(Base):
    """A retrievable text chunk + its embedding. Many rows per Document."""

    __tablename__ = "chunks"
    __table_args__ = (
        # One row per (document, chunk_index): reprocessing must replace, not
        # duplicate. Enforced at DB level so concurrent retries are safe.
        UniqueConstraint("document_id", "chunk_index", name="uq_chunks_doc_idx"),
        # Plain btree index on document_id for "fetch all chunks of doc X".
        Index("ix_chunks_document_id", "document_id"),
        # HNSW vector index is added manually in the Alembic migration via
        # op.execute(...) — SQLAlchemy/Alembic autogenerate does not emit the
        # operator class (vector_cosine_ops) or WITH (m=..., ef_construction=...)
        # parameters needed for production-grade ANN search.
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(EMBEDDING_DIM), nullable=False
    )

    # Free-form per-chunk context (page_number, section_heading, sheet_name,
    # ocr_confidence, etc.). JSONB so we can query on it later without
    # migrating the schema each time we want a new field.
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped["Level2Document"] = relationship(back_populates="chunks")
