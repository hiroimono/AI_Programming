"""Document upload + management for a bot's RAG knowledge base (tenant-scoped).

Every route depends on `get_current_admin`, which pins the RLS tenant GUC
for the request. tenant_id comes from the authenticated admin (never the
body/query), and RLS enforces the same boundary at the DB layer.

Upload flow (synchronous for the MVP):
    multipart file -> validate type + size -> storage.save(bytes)
    -> pipeline.ingest_document (parse -> chunk -> embed -> store)
    -> return the resulting Document row.

Ingestion is awaited inline. For large files this makes the request slow;
moving it to a background task / queue is a documented later enhancement.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import PurePosixPath
from uuid import UUID

from chatbot import pipeline
from chatbot.db import get_session, set_current_tenant
from chatbot.deps import CurrentAdmin, get_current_admin
from chatbot.models import Bot, Document
from chatbot.schemas import DocumentOut
from chatbot.storage import get_storage
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/bots/{bot_id}/documents", tags=["documents"])

# Accepted upload extensions — mirrors the parser dispatch table. An
# upload outside this set is rejected before we touch storage or OpenAI.
_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".txt", ".md", ".csv"}

# Hard cap per upload. 10 MB covers typical handbooks/policies while
# keeping the in-memory read + embedding cost bounded for the MVP.
_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

_BOT_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found"
)
_DOC_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
)


async def _ensure_bot(session: AsyncSession, tenant_id: UUID, bot_id: UUID) -> None:
    """404 if the bot does not exist for this tenant (RLS + explicit filter)."""
    exists = (
        await session.execute(
            select(Bot.id).where(Bot.id == bot_id, Bot.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if exists is None:
        raise _BOT_NOT_FOUND


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    bot_id: UUID,
    file: UploadFile = File(...),
    current: CurrentAdmin = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> DocumentOut:
    """Upload one training file; parse, chunk, embed, and store it."""
    await _ensure_bot(session, current.tenant_id, bot_id)

    filename = file.filename or "unnamed"
    ext = PurePosixPath(filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type {ext!r}. "
            f"Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty",
        )
    if len(content) > _MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {_MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB limit",
        )

    # Persist raw bytes first so we can re-process without re-upload.
    storage_path = get_storage().save(
        content, str(current.tenant_id), str(bot_id), filename
    )

    doc_id = await pipeline.ingest_document(
        tenant_id=current.tenant_id,
        bot_id=bot_id,
        content=content,
        filename=filename,
        mime_type=file.content_type,
        storage_path=storage_path,
    )

    # pipeline committed on its own sessions; re-pin the request session's
    # GUC before reading the freshly-written row back.
    await set_current_tenant(session, current.tenant_id)
    doc = (
        await session.execute(
            select(Document).where(
                Document.id == doc_id, Document.tenant_id == current.tenant_id
            )
        )
    ).scalar_one()
    return DocumentOut.model_validate(doc)


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    bot_id: UUID,
    current: CurrentAdmin = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[DocumentOut]:
    """List a bot's non-deleted documents, newest first."""
    await _ensure_bot(session, current.tenant_id, bot_id)
    docs = (
        (
            await session.execute(
                select(Document)
                .where(
                    Document.bot_id == bot_id,
                    Document.tenant_id == current.tenant_id,
                    Document.deleted_at.is_(None),
                )
                .order_by(Document.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [DocumentOut.model_validate(doc) for doc in docs]


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    bot_id: UUID,
    document_id: UUID,
    current: CurrentAdmin = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> DocumentOut:
    doc = (
        await session.execute(
            select(Document).where(
                Document.id == document_id,
                Document.bot_id == bot_id,
                Document.tenant_id == current.tenant_id,
                Document.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        raise _DOC_NOT_FOUND
    return DocumentOut.model_validate(doc)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_document(
    bot_id: UUID,
    document_id: UUID,
    current: CurrentAdmin = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Soft-delete a document (set deleted_at).

    The chunks/embeddings stay in the table but become unreachable once
    retrieval filters on documents.deleted_at IS NULL (M5). The original
    blob is kept for possible re-processing.
    """
    result = await session.execute(
        update(Document)
        .where(
            Document.id == document_id,
            Document.bot_id == bot_id,
            Document.tenant_id == current.tenant_id,
            Document.deleted_at.is_(None),
        )
        .values(deleted_at=datetime.now(timezone.utc))
    )
    await session.commit()
    if result.rowcount == 0:
        raise _DOC_NOT_FOUND
    return Response(status_code=status.HTTP_204_NO_CONTENT)
