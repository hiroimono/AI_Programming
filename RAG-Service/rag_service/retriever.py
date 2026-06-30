"""Semantic retrieval over rag_level2_writer / rag_level3_chatbot chunks.

Given an embedded user query, returns the top-k most relevant chunks
filtered by tenant (app_id + user_id), optional conversation scope, soft
deletes, AND a hard distance ceiling. The distance ceiling is the
hallucination guard — if no chunk is "close enough" we return [] and
the caller is expected to NOT call the LLM (or to call it with no RAG
context). This is the single most important safety lever for RAG.

pgvector / SQLAlchemy notes:
  - `chunk.embedding.cosine_distance(query_vec)` produces the SQL `<=>`
    operator. The HNSW index built in the initial migration uses
    `vector_cosine_ops`, so this exact operator hits the index.
  - We compute the distance expression once and reuse it both in
    WHERE (filter) and ORDER BY (rank); PostgreSQL's planner evaluates
    it a single time per row.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from rag_service.models import Level2Chunk, Level2Document, Level3Chunk, Level3Document
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Top-k chunks per query. 4 is the sweet spot for a 500-token chunk
# size + ~2k-token LLM context window: enough variety, no dilution.
DEFAULT_K = 4

# Cosine distance ceiling. 0.0 = identical, 2.0 = opposite.
# Empirically 0.4 keeps the LLM from being grounded on weakly-related
# chunks (which is the leading cause of plausible-but-wrong answers).
DEFAULT_MAX_DISTANCE = 0.4

# Per-schema (Document, Chunk) model pair. Adding a Level-4 schema later
# means: new models file, one entry here, no other call-site changes.
_MODELS: dict[str, tuple[type, type]] = {
    "level2": (Level2Document, Level2Chunk),
    "level3": (Level3Document, Level3Chunk),
}


@dataclass
class RetrievedChunk:
    """One chunk returned to a caller. `distance` lets the caller see
    how confident retrieval was (lower = better)."""

    content: str
    distance: float
    document_id: UUID
    document_filename: str
    chunk_index: int
    metadata: dict


async def retrieve(
    session: AsyncSession,
    *,
    app_id: str,
    user_id: str,
    query_vector: list[float],
    conversation_id: UUID | None = None,
    k: int = DEFAULT_K,
    max_distance: float = DEFAULT_MAX_DISTANCE,
    schema: Literal["level2", "level3"] = "level2",
) -> list[RetrievedChunk]:
    """Return top-k chunks for `query_vector`, filtered by tenant scope."""
    doc_model, chunk_model = _MODELS[schema]

    # Build the distance expression once; reuse for filter + ORDER BY so
    # the HNSW index is engaged and no double computation happens.
    distance_expr = chunk_model.embedding.cosine_distance(query_vector)

    stmt = (
        select(
            chunk_model,
            doc_model.file_name,
            distance_expr.label("distance"),
        )
        .join(doc_model, doc_model.id == chunk_model.document_id)
        .where(
            doc_model.app_id == app_id,
            doc_model.user_id == user_id,
            doc_model.deleted_at.is_(None),
            distance_expr < max_distance,
        )
        .order_by(distance_expr)
        .limit(k)
    )

    # conversation_id is optional: when set, scope retrieval to that
    # conversation's uploaded docs only. When None, the user's whole
    # private library is in scope.
    if conversation_id is not None:
        stmt = stmt.where(doc_model.conversation_id == conversation_id)

    result = await session.execute(stmt)
    rows = result.all()

    return [
        RetrievedChunk(
            content=chunk.content,
            distance=float(distance),
            document_id=chunk.document_id,
            document_filename=file_name,
            chunk_index=chunk.chunk_index,
            metadata=chunk.chunk_metadata or {},
        )
        for chunk, file_name, distance in rows
    ]
