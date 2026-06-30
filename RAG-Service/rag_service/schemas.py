"""HTTP request/response models for rag-service endpoints.

Pydantic models here form the public API contract. Two reasons to keep
them separate from the ORM models:
  1. ORM models contain DB-only fields (embedding, deleted_at) that
     should never leak across the wire.
  2. Wire shapes can change independently from DB schema (versioning).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ───────────────────────── Documents ─────────────────────────────────


class IngestResponse(BaseModel):
    """Returned by POST /api/documents after ingestion completes."""

    document_id: UUID
    status: str
    chunk_count: int


class DocumentItem(BaseModel):
    """A single row in GET /api/documents listing."""

    # from_attributes lets pydantic build this from a SQLAlchemy ORM
    # object without a manual mapping step.
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_name: str
    file_type: str
    mime_type: str
    file_size_bytes: int
    status: str
    chunk_count: int
    created_at: datetime
    error_message: str | None = None


class DocumentListResponse(BaseModel):
    """Envelope for GET /api/documents (lets us add pagination later
    without changing the response shape)."""

    documents: list[DocumentItem]


class DocumentChunkOut(BaseModel):
    """One chunk of a document, in GET /api/documents/{id}/chunks order."""

    chunk_index: int
    content: str
    content_tokens: int


class DocumentChunksResponse(BaseModel):
    """Envelope for GET /api/documents/{id}/chunks. Chunks are sorted
    by chunk_index so a client can concatenate them to reconstruct the
    parsed-text view of the document."""

    document_id: UUID
    file_name: str
    chunks: list[DocumentChunkOut]


# ───────────────────────── Retrieval ─────────────────────────────────


class RetrieveRequest(BaseModel):
    """POST /api/retrieve body. app_id / user_id come from the JWT, NOT
    from this body — clients cannot pretend to be another user."""

    query: str = Field(min_length=1, max_length=2000)
    k: int = Field(default=4, ge=1, le=20)
    max_distance: float = Field(
        default=0.4,
        ge=0.0,
        le=2.0,
        description="Cosine distance ceiling; chunks above this are filtered out.",
    )


class RetrievedChunkOut(BaseModel):
    """One chunk in a retrieval response."""

    content: str
    distance: float
    document_id: UUID
    document_filename: str
    chunk_index: int
    metadata: dict[str, Any]


class RetrieveResponse(BaseModel):
    """Envelope for POST /api/retrieve. Empty `chunks` means the caller
    should NOT call the LLM with RAG context (hallucination guard fired)."""

    chunks: list[RetrievedChunkOut]
