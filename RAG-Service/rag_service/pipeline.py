"""End-to-end RAG pipeline: ingestion + retrieval orchestrators.

This module is what every endpoint in Phase 4 will call. Endpoints stay
thin (validate request → call pipeline → format response); all the
parser→chunker→embedder→DB and embedder→retriever wiring lives here.

Two entrypoints:

  ingest_document(...)   raw bytes ----> stored doc + N embedded chunks
  retrieve_context(...)  user query ---> top-k relevant chunks

Both manage their own DB transactions via `session_factory` so callers
(FastAPI endpoints) do not have to handle session lifetimes for these
operations. Each commit is small and well-bounded:
  - One transaction to register the Document (status='uploaded')
  - One transaction to write all chunks + flip status to 'ready'
  - One transaction (on failure) to flip status to 'error'

This keeps the document row visible to listing endpoints even if the
embedding step crashes — the user can see "this upload failed" instead
of nothing.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Literal
from uuid import UUID

from rag_service.chunker import chunk_text
from rag_service.db import session_factory
from rag_service.embedder import embed_batch, embed_one
from rag_service.models import Level2Chunk, Level2Document, Level3Chunk, Level3Document
from rag_service.parsers import parse
from rag_service.retriever import (
    DEFAULT_K,
    DEFAULT_MAX_DISTANCE,
    RetrievedChunk,
    retrieve,
)
from rag_service.storage import get_storage
from sqlalchemy import update

# Mirror of retriever._MODELS — kept duplicated (vs imported) so pipeline
# remains decoupled from retriever's private state. Both modules dispatch
# on the same Literal schema key.
_MODELS: dict[str, tuple[type, type]] = {
    "level2": (Level2Document, Level2Chunk),
    "level3": (Level3Document, Level3Chunk),
}

# Per-app schema dispatch. Adding a Level-4 app means: new schema in
# models/, register the (Document, Chunk) pair in _MODELS above + here.
_APP_TO_SCHEMA: dict[str, str] = {
    "level-2-writer": "level2",
    "level-3-chatbot": "level3",
}


def schema_for_app(app_id: str) -> str:
    """Map an app_id (from JWT) to the RAG schema key it owns.

    Routers call this to translate identity.app_id into the schema
    parameter that ingest_document / retrieve_context expect. Raises
    ValueError for unknown apps so the endpoint layer can return 403.
    """
    try:
        return _APP_TO_SCHEMA[app_id]
    except KeyError as exc:
        raise ValueError(f"Unknown app_id: {app_id!r}") from exc


# Truncate error messages stored in DB so a 50-line stack trace doesn't
# blow up the documents.error_message column (defined as TEXT but UI
# should never need to render an essay).
_ERROR_MSG_MAX_LEN = 500


def _file_type_from_name(filename: str) -> str:
    """Lowercase extension without the dot. Falls back to 'unknown'."""
    ext = PurePosixPath(filename).suffix.lower().lstrip(".")
    return ext or "unknown"


async def ingest_document(
    *,
    app_id: str,
    user_id: str,
    conversation_id: UUID | None,
    content: bytes,
    filename: str,
    mime_type: str | None,
    schema: Literal["level2", "level3"] = "level2",
) -> UUID:
    """Parse → chunk → embed → store. Returns the new document_id.

    On any failure after the Document row is created, the row is updated
    with status='error' and an error_message snippet, then the exception
    is re-raised so the calling endpoint can return a 500.
    """
    doc_model, chunk_model = _MODELS[schema]
    storage = get_storage()

    # 1. Persist raw bytes first — even if subsequent steps fail we still
    #    have the original file for re-processing without re-upload.
    storage_path = storage.save(content, app_id, user_id, filename)

    # 2. Register the document (status='uploaded') in its own commit so
    #    list endpoints see it immediately, even before embedding finishes.
    async with session_factory() as session:
        doc = doc_model(
            app_id=app_id,
            user_id=user_id,
            conversation_id=conversation_id,
            file_name=filename,
            file_type=_file_type_from_name(filename),
            mime_type=mime_type or "application/octet-stream",
            file_size_bytes=len(content),
            status="uploaded",
            storage_path=storage_path,
        )
        session.add(doc)
        await session.flush()
        doc_id = doc.id
        await session.commit()

    try:
        # 3. Parse + chunk in memory (no DB I/O).
        parsed = parse(content, mime_type, filename)
        chunks = chunk_text(
            parsed.full_text,
            base_metadata={
                "parser": parsed.parser,
                "page_count": parsed.page_count,
            },
        )

        # 4a. Empty document path — nothing to embed, mark ready with 0.
        if not chunks:
            async with session_factory() as session:
                await session.execute(
                    update(doc_model)
                    .where(doc_model.id == doc_id)
                    .values(status="ready", chunk_count=0)
                )
                await session.commit()
            return doc_id

        # 4b. Embed all chunks in batched OpenAI calls.
        embeddings = await embed_batch([c.content for c in chunks])

        # 5. Write chunks + flip status atomically.
        async with session_factory() as session:
            chunk_rows = [
                chunk_model(
                    document_id=doc_id,
                    chunk_index=c.chunk_index,
                    content=c.content,
                    content_tokens=c.content_tokens,
                    embedding=emb,
                    chunk_metadata=c.metadata,
                )
                for c, emb in zip(chunks, embeddings)
            ]
            session.add_all(chunk_rows)
            await session.execute(
                update(doc_model)
                .where(doc_model.id == doc_id)
                .values(status="ready", chunk_count=len(chunks))
            )
            await session.commit()

        return doc_id

    except Exception as exc:  # pylint: disable=broad-exception-caught
        # Surface the failure to the user via document status; re-raise
        # so the endpoint layer can turn it into a 500 + log.
        async with session_factory() as session:
            await session.execute(
                update(doc_model)
                .where(doc_model.id == doc_id)
                .values(
                    status="error",
                    error_message=str(exc)[:_ERROR_MSG_MAX_LEN],
                )
            )
            await session.commit()
        raise


async def retrieve_context(
    *,
    app_id: str,
    user_id: str,
    query: str,
    conversation_id: UUID | None = None,
    k: int = DEFAULT_K,
    max_distance: float = DEFAULT_MAX_DISTANCE,
    schema: Literal["level2", "level3"] = "level2",
) -> list[RetrievedChunk]:
    """Embed `query` and return top-k chunks. Empty list = no good match
    found → caller should skip the LLM (or call it without context)."""
    query_vector = await embed_one(query)
    async with session_factory() as session:
        return await retrieve(
            session,
            app_id=app_id,
            user_id=user_id,
            query_vector=query_vector,
            conversation_id=conversation_id,
            k=k,
            max_distance=max_distance,
            schema=schema,
        )
