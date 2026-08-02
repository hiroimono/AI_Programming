"""Document ingestion pipeline: upload bytes -> stored, embedded chunks.

Endpoints stay thin (validate request -> call pipeline -> format
response); all parser->chunker->embedder->DB wiring lives here.

RLS + transaction rule (critical):
    Every `async with session_factory()` block below re-pins the tenant
    via `set_current_tenant()` FIRST. The RLS GUC is set with
    is_local=true, so it is transaction-scoped and cleared on commit —
    a later block on a pooled connection would otherwise see no tenant
    and every RLS-protected INSERT/UPDATE would be rejected.

Transaction boundaries are deliberately small so the Document row stays
visible to list endpoints even if a later step crashes:
  - One commit registers the Document (status='uploaded').
  - One commit writes all chunks + UsageEvents + flips status to 'ready'.
  - One commit (on failure) flips status to 'failed' with an error snippet.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from uuid import UUID

from chatbot.chunker import chunk_text
from chatbot.config import get_settings
from chatbot.db import session_factory, set_current_tenant
from chatbot.embedder import embed_batch
from chatbot.models import Chunk, Document, UsageEvent
from chatbot.parsers import parse
from sqlalchemy import update

# Truncate error messages stored in DB so a 50-line stack trace does not
# fill the documents.error_message column.
_ERROR_MSG_MAX_LEN = 500


def _file_type_from_name(filename: str) -> str:
    """Lowercase extension without the dot. Falls back to 'unknown'."""
    ext = PurePosixPath(filename).suffix.lower().lstrip(".")
    return ext or "unknown"


async def ingest_document(
    *,
    tenant_id: UUID,
    bot_id: UUID,
    content: bytes,
    filename: str,
    mime_type: str | None,
    storage_path: str,
) -> UUID:
    """Parse -> chunk -> embed -> store. Returns the new document_id.

    The raw bytes are expected to already be persisted (the endpoint saves
    them via storage.save and passes the resulting storage_path). On any
    failure after the Document row exists, the row is flipped to
    status='failed' with an error snippet and the exception is re-raised
    so the endpoint can return a 500.
    """
    # 1. Register the document (status='uploaded') in its own commit so
    #    list endpoints see it immediately, even before embedding finishes.
    async with session_factory() as session:
        await set_current_tenant(session, tenant_id)
        doc = Document(
            tenant_id=tenant_id,
            bot_id=bot_id,
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
        # 2. Parse + chunk in memory (no DB I/O).
        parsed = parse(content, mime_type, filename)
        chunks = chunk_text(
            parsed.full_text,
            base_metadata={
                "parser": parsed.parser,
                "page_count": parsed.page_count,
            },
        )

        # 3a. Empty document path — nothing to embed, mark ready with 0.
        if not chunks:
            async with session_factory() as session:
                await set_current_tenant(session, tenant_id)
                await session.execute(
                    update(Document)
                    .where(Document.id == doc_id)
                    .values(status="ready", chunk_count=0)
                )
                session.add(
                    UsageEvent(
                        tenant_id=tenant_id,
                        bot_id=bot_id,
                        event_type="document_upload",
                    )
                )
                await session.commit()
            return doc_id

        # 3b. Embed all chunks in batched OpenAI calls.
        embeddings = await embed_batch([c.content for c in chunks])
        total_tokens = sum(c.content_tokens for c in chunks)
        embedding_model = get_settings().openai_embedding_model

        # 4. Write chunks + UsageEvents + flip status atomically.
        async with session_factory() as session:
            await set_current_tenant(session, tenant_id)
            session.add_all(
                [
                    Chunk(
                        tenant_id=tenant_id,
                        document_id=doc_id,
                        bot_id=bot_id,
                        chunk_index=c.chunk_index,
                        content=c.content,
                        content_tokens=c.content_tokens,
                        embedding=emb,
                    )
                    for c, emb in zip(chunks, embeddings)
                ]
            )
            await session.execute(
                update(Document)
                .where(Document.id == doc_id)
                .values(status="ready", chunk_count=len(chunks))
            )
            session.add_all(
                [
                    UsageEvent(
                        tenant_id=tenant_id,
                        bot_id=bot_id,
                        event_type="embedding",
                        model=embedding_model,
                        embedding_tokens=total_tokens,
                    ),
                    UsageEvent(
                        tenant_id=tenant_id,
                        bot_id=bot_id,
                        event_type="document_upload",
                    ),
                ]
            )
            await session.commit()

        return doc_id

    except Exception as exc:  # pylint: disable=broad-exception-caught
        # Surface the failure via document status; re-raise so the endpoint
        # layer can turn it into a 500 + log.
        async with session_factory() as session:
            await set_current_tenant(session, tenant_id)
            await session.execute(
                update(Document)
                .where(Document.id == doc_id)
                .values(
                    status="failed",
                    error_message=str(exc)[:_ERROR_MSG_MAX_LEN],
                )
            )
            await session.commit()
        raise
