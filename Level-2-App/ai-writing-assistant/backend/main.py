# main.py — FastAPI Application Entry Point (SSE Streaming)
# ============================================================
# Equivalent of Program.cs in .NET.
#
# Key concept: Server-Sent Events (SSE)
# ─────────────────────────────────────
# SSE is a one-way streaming protocol (server → client) over HTTP.
# Unlike WebSocket (bidirectional), SSE uses a standard GET/POST request
# and the server keeps the connection open, pushing "events" as they arrive.
#
# Format: each event is "data: <content>\n\n"
# End signal: "data: [DONE]\n\n"
#
# .NET comparison:
#   app.MapPost("/api/chat", async (HttpContext ctx) => {
#       ctx.Response.ContentType = "text/event-stream";
#       await foreach (var chunk in aiService.StreamAsync(request))
#           await ctx.Response.WriteAsync($"data: {chunk}\n\n");
#   });

import json
from contextlib import asynccontextmanager
from typing import Annotated, AsyncIterator
from urllib.parse import quote
from uuid import UUID

from auth import GatewayUser, optional_user, require_user
from config import settings
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from models import (
    ChatRequest,
    DocumentChunksResponse,
    DocumentItem,
    DocumentListResponse,
    DocumentUploadResponse,
    GenerateTitleRequest,
    GenerateTitleResponse,
    HealthResponse,
    SourceCitation,
)
from rag_client import (
    RetrievedChunk,
    get_rag_client,
    shutdown_rag_client,
    startup_rag_client,
)
from writer import generate_title, stream_chat


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Initialize / dispose the rag-service HTTP client pool."""
    await startup_rag_client()
    try:
        yield
    finally:
        await shutdown_rag_client()


app = FastAPI(
    title="AI Writing Assistant",
    description="SSE Streaming AI Writing Service",
    version="1.1.0",
    lifespan=lifespan,
)

# CORS — Allow Gateway and local Angular dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://localhost:4201",
        "http://localhost:5000",
        "https://gateway-production-072b.up.railway.app",
        "https://ai-classifier.pages.dev",
        "https://ai-writing-assistant.pages.dev",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Top-k chunks to pull from rag-service for each chat turn. 4 is the
# rag-service default and keeps the prompt small enough to leave room
# for the conversation history.
_RAG_K = 4
# Cosine distance ceiling. Below this we trust the chunk is "actually
# relevant"; above this rag-service drops it and the hallucination
# guard kicks in. Empirically with text-embedding-3-small even tightly
# relevant chunks sit around 0.30 – 0.45, so 0.4 (rag-service default)
# is too strict for real questions. For generic intents like
# "summarize this document" the query has little lexical overlap with
# the doc text, so distances climb above 1.0 even for the right doc.
# 1.5 keeps recall for that case while still rejecting genuinely
# unrelated chunks (those land closer to the 2.0 ceiling).
_RAG_MAX_DISTANCE = 1.5
# How many leading characters of each chunk we send back to the FE in
# the `sources` SSE event. Enough for a tooltip, small enough to keep
# the wire payload tiny.
_SOURCE_PREVIEW_CHARS = 200


def _format_rag_context(chunks: list[RetrievedChunk]) -> str:
    """Inline-format retrieved chunks for injection into the system prompt."""
    parts: list[str] = []
    for i, c in enumerate(chunks, start=1):
        parts.append(f"[Source {i} | file: {c.document_filename}]\n{c.content}")
    return "\n\n".join(parts)


def _build_citations(chunks: list[RetrievedChunk]) -> list[SourceCitation]:
    """Trim chunk content to a short preview for the FE accordion."""
    return [
        SourceCitation(
            document_id=UUID(c.document_id),
            document_filename=c.document_filename,
            chunk_index=c.chunk_index,
            distance=c.distance,
            preview=c.content[:_SOURCE_PREVIEW_CHARS],
        )
        for c in chunks
    ]


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="healthy", service="ai-writing-assistant")


@app.post("/api/chat")
async def chat_stream(
    request: ChatRequest,
    user: Annotated[GatewayUser | None, Depends(optional_user)] = None,
):
    """
    SSE streaming chat endpoint.

    The client sends conversation history + writing mode,
    and receives tokens streamed back in real-time.

    When a Bearer JWT is present AND `conversation_id` is set, the
    last user message is used to retrieve top-k document chunks from
    rag-service. Those chunks are injected into the system prompt and
    a `sources` event is emitted before `[DONE]` so the FE can render
    citations.

    Response format: text/event-stream
      data: {"content": "Hello"}
      data: {"content": " world"}
      event: sources
      data: [{"document_id": "...", "document_filename": "...", ...}]
      data: [DONE]
    """
    if not settings.validate():
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    # Retrieve RAG context up-front (before the stream opens) so we can
    # both inject it into the prompt and emit citations on the stream.
    rag_context: str | None = None
    citations: list[SourceCitation] = []
    if (
        user is not None
        and request.conversation_id is not None
        and settings.rag_enabled()
        and messages
    ):
        # Use the most recent user message as the retrieval query.
        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"),
            None,
        )
        if last_user:
            client = get_rag_client()
            chunks = await client.retrieve(
                user_id=user.user_id,
                conversation_id=request.conversation_id,
                query=last_user,
                k=_RAG_K,
                max_distance=_RAG_MAX_DISTANCE,
            )
            if chunks:
                rag_context = _format_rag_context(chunks)
                citations = _build_citations(chunks)

    async def event_generator():
        async for token in stream_chat(messages, request.writing_mode, rag_context):
            # SSE format: "data: <json>\n\n"
            yield f"data: {json.dumps({'content': token})}\n\n"
        # Emit citations (may be empty) so the FE can clear stale ones.
        sources_payload = [c.model_dump(mode="json") for c in citations]
        yield f"event: sources\ndata: {json.dumps(sources_payload)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering if proxied
        },
    )


@app.post("/api/generate-title", response_model=GenerateTitleResponse)
async def generate_chat_title(request: GenerateTitleRequest):
    """
    Generates a concise conversation title from the message history.
    Returns the title along with relevance scores for the new and current titles.
    """
    if not settings.validate():
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    result = await generate_title(messages, request.current_title)
    return GenerateTitleResponse(**result)


# ── Phase 5: document management endpoints ─────────────────────────
#
# These proxy to rag-service. The Gateway JWT is required; user_id
# from the token is forwarded so rag-service scopes everything to
# the right tenant. The Level-2 BE never reads or stores document
# content itself — it only routes.


@app.post(
    "/api/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    user: Annotated[GatewayUser, Depends(require_user)],
    file: UploadFile = File(...),
    conversation_id: UUID | None = Form(default=None),
):
    """Upload a document and ingest it into the user's RAG index."""
    content = await file.read()
    client = get_rag_client()
    result = await client.upload_document(
        user_id=user.user_id,
        conversation_id=conversation_id,
        filename=file.filename or "unnamed",
        content=content,
        mime_type=file.content_type,
    )
    return DocumentUploadResponse(**result)


@app.get("/api/documents", response_model=DocumentListResponse)
async def list_documents(
    user: Annotated[GatewayUser, Depends(require_user)],
    conversation_id: UUID | None = None,
):
    """List the caller's documents, optionally filtered by conversation."""
    client = get_rag_client()
    docs = await client.list_documents(
        user_id=user.user_id,
        conversation_id=conversation_id,
    )
    return DocumentListResponse(documents=[DocumentItem(**d.__dict__) for d in docs])


@app.delete(
    "/api/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_document(
    document_id: UUID,
    user: Annotated[GatewayUser, Depends(require_user)],
) -> Response:
    """Soft-delete one of the caller's documents."""
    client = get_rag_client()
    await client.delete_document(user_id=user.user_id, document_id=document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get(
    "/api/documents/{document_id}/chunks",
    response_model=DocumentChunksResponse,
)
async def get_document_chunks(
    document_id: UUID,
    user: Annotated[GatewayUser, Depends(require_user)],
) -> DocumentChunksResponse:
    """Returns the chunked parsed-text view of one of the caller's
    documents, used by the FE preview modal. Tenant-scoped (404 if
    the doc doesn't belong to the caller)."""
    client = get_rag_client()
    payload = await client.get_document_chunks(
        user_id=user.user_id,
        document_id=document_id,
    )
    return DocumentChunksResponse(**payload)


@app.get("/api/documents/{document_id}/file")
async def get_document_file(
    document_id: UUID,
    user: Annotated[GatewayUser, Depends(require_user)],
) -> Response:
    """Streams the original uploaded file back to the browser so the FE
    can render PDFs / images / text inline. Tenant-scoped (404 if the
    doc doesn't belong to the caller)."""
    client = get_rag_client()
    content, content_type, filename = await client.get_document_file(
        user_id=user.user_id,
        document_id=document_id,
    )
    # HTTP headers must be latin-1; encode unicode filenames per RFC 5987.
    ascii_fallback = filename.encode("ascii", "replace").decode("ascii").replace('"', "")
    quoted_utf8 = quote(filename, safe="")
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": (
                f'inline; filename="{ascii_fallback}"; '
                f"filename*=UTF-8''{quoted_utf8}"
            ),
            "Cache-Control": "private, max-age=300",
        },
    )
