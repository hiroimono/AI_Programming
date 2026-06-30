"""Document management endpoints: upload, list, soft-delete.

All endpoints require a valid internal JWT and operate within the
(app_id, user_id) tuple extracted from it — there is no way for a
client to act on behalf of a different user or app.
"""

# pylint: disable=not-callable
# SQLAlchemy's `func` namespace generates attributes dynamically
# (func.now, func.coalesce, ...). Pylint can't see them as callable.

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import func, select, update

from rag_service.auth import AuthedIdentity
from rag_service.db import session_factory
from rag_service.models import (
    Level2Chunk,
    Level2Document,
    Level3Chunk,
    Level3Document,
)
from rag_service.parsers import UnsupportedFileTypeError
from rag_service.pipeline import ingest_document, schema_for_app
from rag_service.schemas import (
    DocumentItem,
    DocumentListResponse,
    IngestResponse,
)

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
