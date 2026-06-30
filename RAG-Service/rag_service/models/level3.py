"""Level-3 (Customer-Facing Chatbot) RAG schema: documents + chunks.

Schema: rag_level3_chatbot

Structurally identical to level2 but in its own schema for tenant isolation
and independent migration evolution. See models/level2.py for design notes.
"""

# pylint: disable=not-callable
# SQLAlchemy's `func` namespace generates attributes dynamically.

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

SCHEMA = "rag_level3_chatbot"

EMBEDDING_DIM = 1536


class Level3Document(Base):
    """Uploaded source file. One row per file the user attaches in chat."""

    __tablename__ = "documents"
    __table_args__ = (
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

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="uploaded")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    chunks: Mapped[list["Level3Chunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Level3Chunk(Base):
    """A retrievable text chunk + its embedding. Many rows per Document."""

    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunks_doc_idx"),
        Index("ix_chunks_document_id", "document_id"),
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

    document: Mapped["Level3Document"] = relationship(back_populates="chunks")
