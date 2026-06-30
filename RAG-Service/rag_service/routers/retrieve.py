"""Semantic retrieval endpoint.

Embeds the query, finds top-k chunks in the caller's tenant scope,
applies the distance ceiling, returns the chunks. The caller (typically
the consuming app's backend) then assembles a prompt and calls its
own LLM provider — rag-service intentionally does NOT call the LLM.
This keeps secrets, billing, and model choice owned by each app.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from rag_service.auth import AuthedIdentity
from rag_service.pipeline import retrieve_context, schema_for_app
from rag_service.schemas import RetrievedChunkOut, RetrieveRequest, RetrieveResponse

router = APIRouter(prefix="/api", tags=["retrieve"])


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
    "/retrieve",
    response_model=RetrieveResponse,
    summary="Find top-k chunks relevant to a query. app_id/user_id from JWT.",
)
async def retrieve_endpoint(
    body: RetrieveRequest,
    identity: AuthedIdentity,
) -> RetrieveResponse:
    """Embeds `body.query` and runs vector retrieval scoped to the
    JWT-bound user. Returns an empty list when nothing meets the
    distance ceiling — the hallucination guard."""
    schema = _resolve_schema(identity.app_id)

    chunks = await retrieve_context(
        app_id=identity.app_id,
        user_id=identity.user_id,
        conversation_id=identity.conversation_id,
        query=body.query,
        k=body.k,
        max_distance=body.max_distance,
        schema=schema,  # type: ignore[arg-type]
    )

    return RetrieveResponse(
        chunks=[
            RetrievedChunkOut(
                content=c.content,
                distance=c.distance,
                document_id=c.document_id,
                document_filename=c.document_filename,
                chunk_index=c.chunk_index,
                metadata=c.metadata,
            )
            for c in chunks
        ]
    )
