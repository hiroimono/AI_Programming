"""Document management endpoints: upload, list, soft-delete.

All endpoints require a valid internal JWT and operate within the
(app_id, user_id) tuple extracted from it — there is no way for a
client to act on behalf of a different user or app.
"""

# pylint: disable=not-callable
# SQLAlchemy's `func` namespace generates attributes dynamically
# (func.now, func.coalesce, ...). Pylint can't see them as callable.

from __future__ import annotations

from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status
from rag_service.auth import AuthedIdentity
from rag_service.db import session_factory
from rag_service.models import Level2Chunk, Level2Document, Level3Chunk, Level3Document
from rag_service.parsers import UnsupportedFileTypeError
from rag_service.pipeline import ingest_document, schema_for_app
from rag_service.schemas import (
    DocumentChunkOut,
    DocumentChunksResponse,
    DocumentItem,
    DocumentListResponse,
    IngestResponse,
)
from rag_service.storage import get_storage
from sqlalchemy import func, select, update

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Reuse the same schema → model mapping pipeline.py uses internally.
# Duplicated to keep this router decoupled from pipeline's private dict.
_MODELS: dict[str, tuple[type, type]] = {
    "level2": (Level2Document, Level2Chunk),
    "level3": (Level3Document, Level3Chunk),
}

# Hard cap on how many docs we'll list in one call. Pagination can be
# added later behind the same envelope (DocumentListResponse).
_LIST_LIMIT = 100


def _resolve_schema(app_id: str) -> str:
    """Translate identity.app_id into a schema key or raise 403."""
    try:
        return schema_for_app(app_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


@router.post(
    "",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document and ingest it into the RAG index.",
)
async def upload_document(
    identity: AuthedIdentity,
    file: UploadFile = File(...),
    conversation_id: UUID | None = Form(default=None),
) -> IngestResponse:
    """Multipart upload → parse → chunk → embed → store.

    `conversation_id` from the form overrides the one in the JWT (if
    present). When neither is set the document lives at the user level,
    visible across all of that user's conversations.
    """
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    schema = _resolve_schema(identity.app_id)
    effective_conv_id = conversation_id or identity.conversation_id

    try:
        doc_id = await ingest_document(
            app_id=identity.app_id,
            user_id=identity.user_id,
            conversation_id=effective_conv_id,
            content=content,
            filename=file.filename or "unnamed",
            mime_type=file.content_type,
            schema=schema,  # type: ignore[arg-type]
        )
    except UnsupportedFileTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc

    # Re-read the row to return authoritative status + chunk_count
    # (pipeline updates the row inside its own transactions).
    doc_model, _ = _MODELS[schema]
    async with session_factory() as session:
        doc = await session.get(doc_model, doc_id)
    if doc is None:
        # Should not happen — pipeline just wrote it. Defensive only.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document was created but could not be read back",
        )
    return IngestResponse(
        document_id=doc.id,
        status=doc.status,
        chunk_count=doc.chunk_count,
    )


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List the caller's documents (most recent first).",
)
async def list_documents(
    identity: AuthedIdentity,
    conversation_id: UUID | None = None,
) -> DocumentListResponse:
    """Returns up to _LIST_LIMIT documents, filtered by tenant + scope."""
    schema = _resolve_schema(identity.app_id)
    doc_model, _ = _MODELS[schema]

    async with session_factory() as session:
        stmt = (
            select(doc_model)
            .where(
                doc_model.app_id == identity.app_id,
                doc_model.user_id == identity.user_id,
                doc_model.deleted_at.is_(None),
            )
            .order_by(doc_model.created_at.desc())
            .limit(_LIST_LIMIT)
        )
        if conversation_id is not None:
            stmt = stmt.where(doc_model.conversation_id == conversation_id)
        result = await session.execute(stmt)
        docs = result.scalars().all()

    return DocumentListResponse(
        documents=[DocumentItem.model_validate(d) for d in docs]
    )


@router.get(
    "/{document_id}/chunks",
    response_model=DocumentChunksResponse,
    summary="Return all chunks of a document, ordered by chunk_index.",
)
async def get_document_chunks(
    document_id: UUID,
    identity: AuthedIdentity,
) -> DocumentChunksResponse:
    """Used by clients that want to preview the parsed-text view of a
    document. Tenant-scoped: 404 if the doc doesn't belong to the
    caller (we never leak existence across users)."""
    schema = _resolve_schema(identity.app_id)
    doc_model, chunk_model = _MODELS[schema]

    async with session_factory() as session:
        # Confirm doc exists, belongs to this caller, and isn't soft-deleted.
        doc_stmt = select(doc_model).where(
            doc_model.id == document_id,
            doc_model.app_id == identity.app_id,
            doc_model.user_id == identity.user_id,
            doc_model.deleted_at.is_(None),
        )
        doc = (await session.execute(doc_stmt)).scalar_one_or_none()
        if doc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

        chunks_stmt = (
            select(chunk_model)
            .where(chunk_model.document_id == document_id)
            .order_by(chunk_model.chunk_index)
        )
        chunks = (await session.execute(chunks_stmt)).scalars().all()

    return DocumentChunksResponse(
        document_id=doc.id,
        file_name=doc.file_name,
        chunks=[
            DocumentChunkOut(
                chunk_index=c.chunk_index,
                content=c.content,
                content_tokens=c.content_tokens,
            )
            for c in chunks
        ],
    )


@router.get(
    "/{document_id}/file",
    summary="Stream the originally-uploaded file bytes (for preview / download).",
    responses={
        200: {"content": {"application/octet-stream": {}}},
        404: {"description": "Document not found or storage blob missing"},
    },
)
async def get_document_file(
    document_id: UUID,
    identity: AuthedIdentity,
) -> Response:
    """Returns the original file as raw bytes with the stored mime_type.

    Tenant-scoped: 404 if the doc doesn't belong to the caller. Browsers
    can render PDFs / images directly via Content-Disposition: inline.
    """
    schema = _resolve_schema(identity.app_id)
    doc_model, _ = _MODELS[schema]

    async with session_factory() as session:
        doc_stmt = select(doc_model).where(
            doc_model.id == document_id,
            doc_model.app_id == identity.app_id,
            doc_model.user_id == identity.user_id,
            doc_model.deleted_at.is_(None),
        )
        doc = (await session.execute(doc_stmt)).scalar_one_or_none()

    if doc is None or not doc.storage_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    try:
        content = get_storage().read(doc.storage_path)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored file is missing",
        ) from exc

    # Content-Disposition: ASCII fallback + RFC 5987 unicode hint.
    # Non-ASCII filenames (e.g. "Risale-i Nur\u2019da\u2026.pdf") cannot go
    # directly into HTTP headers (latin-1 only).
    original = doc.file_name or "document"
    ascii_fallback = (
        original.encode("ascii", "replace").decode("ascii").replace('"', "")
    )
    quoted_utf8 = quote(original, safe="")
    return Response(
        content=content,
        media_type=doc.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": (
                f'inline; filename="{ascii_fallback}"; '
                f"filename*=UTF-8''{quoted_utf8}"
            ),
            "Cache-Control": "private, max-age=300",
        },
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Soft-delete a document. Idempotent; 404 if not found / already deleted.",
)
async def delete_document(
    document_id: UUID,
    identity: AuthedIdentity,
) -> Response:
    """Marks `deleted_at = now()` so retrieval skips this doc but old
    citations still resolve to a file name."""
    schema = _resolve_schema(identity.app_id)
    doc_model, _ = _MODELS[schema]

    async with session_factory() as session:
        result = await session.execute(
            update(doc_model)
            .where(
                doc_model.id == document_id,
                doc_model.app_id == identity.app_id,
                doc_model.user_id == identity.user_id,
                doc_model.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
        )
        if result.rowcount == 0:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
