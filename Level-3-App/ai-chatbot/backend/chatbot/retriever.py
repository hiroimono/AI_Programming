"""Semantic retrieval over a bot's chunks (M5).

Given an embedded user query, returns the top-k most relevant chunks for one
bot, filtered by soft-deletes AND a hard cosine-distance ceiling. The ceiling
is the hallucination guard: if no chunk is "close enough" we return [], and
the caller answers without RAG context (the system prompt tells the model to
admit it doesn't know) instead of grounding on weakly-related text.

Adapted from the proven RAG-Service retriever, re-scoped from app_id/user_id
to bot_id and stripped of the conversation-scope + chunk_metadata bits that
this schema doesn't have. tenant isolation is enforced by RLS; the explicit
bot_id filter narrows retrieval to the one bot the widget session is for.

pgvector / SQLAlchemy notes:
  - `Chunk.embedding.cosine_distance(vec)` emits the SQL `<=>` operator, which
    matches the HNSW `vector_cosine_ops` index from the initial migration.
  - The distance expression is built once and reused in WHERE + ORDER BY, so
    PostgreSQL evaluates it a single time per row and the index is engaged.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from chatbot.models import Chunk, Document
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Top-k chunks per query. 4 balances variety against context dilution for a
# 500-token chunk size + a small chat context window.
DEFAULT_K = 4

# Cosine distance ceiling (0.0 = identical, 2.0 = opposite). Empirically, with
# text-embedding-3-small even tightly relevant chunks sit around 0.30 - 0.45
# for casually-phrased queries (confirmed in Level-2's RAG add-on), so 0.4 is
# too strict and silently drops on-topic chunks. 1.5 keeps genuinely unrelated
# content out (that lands near the 2.0 ceiling) while not starving retrieval.
DEFAULT_MAX_DISTANCE = 1.5


@dataclass
class RetrievedChunk:
    """One chunk returned to the caller; `distance` exposes retrieval
    confidence (lower = closer match)."""

    content: str
    distance: float
    document_id: UUID
    document_filename: str
    chunk_index: int


async def retrieve(
    session: AsyncSession,
    *,
    bot_id: UUID,
    query_vector: list[float],
    k: int = DEFAULT_K,
    max_distance: float = DEFAULT_MAX_DISTANCE,
) -> list[RetrievedChunk]:
    """Return the top-k closest chunks for `query_vector` within one bot."""
    distance_expr = Chunk.embedding.cosine_distance(query_vector)

    stmt = (
        select(
            Chunk.content,
            Chunk.document_id,
            Chunk.chunk_index,
            Document.file_name,
            distance_expr.label("distance"),
        )
        .join(Document, Document.id == Chunk.document_id)
        .where(
            Chunk.bot_id == bot_id,
            Document.deleted_at.is_(None),
            distance_expr < max_distance,
        )
        .order_by(distance_expr)
        .limit(k)
    )

    rows = (await session.execute(stmt)).all()

    return [
        RetrievedChunk(
            content=content,
            distance=float(distance),
            document_id=document_id,
            document_filename=file_name,
            chunk_index=chunk_index,
        )
        for content, document_id, chunk_index, file_name, distance in rows
    ]
