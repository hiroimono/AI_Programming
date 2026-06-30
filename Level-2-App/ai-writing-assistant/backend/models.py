# models.py — Pydantic Models (DTOs)
# ====================================

from uuid import UUID

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    writing_mode: str = "general"  # general, blog, email, report, creative
    # Phase 5: when set, the chat endpoint runs RAG retrieval scoped to
    # this conversation's uploaded documents. None = no RAG, behave as
    # the original anonymous chat.
    conversation_id: UUID | None = None


class GenerateTitleRequest(BaseModel):
    messages: list[ChatMessage]
    current_title: str = ""


class GenerateTitleResponse(BaseModel):
    title: str
    new_score: int  # 0-100 relevance score for the new title
    old_score: int  # 0-100 relevance score for the current title


class HealthResponse(BaseModel):
    status: str
    service: str


# ── Phase 5: document management responses ─────────────────────────


class DocumentUploadResponse(BaseModel):
    document_id: UUID
    status: str
    chunk_count: int


class DocumentItem(BaseModel):
    id: UUID
    file_name: str
    file_type: str
    mime_type: str | None
    file_size_bytes: int
    status: str
    chunk_count: int
    created_at: str
    error_message: str | None


class DocumentListResponse(BaseModel):
    documents: list[DocumentItem]


class DocumentChunkOut(BaseModel):
    """One chunk of a document, returned by the chunks-preview endpoint."""

    chunk_index: int
    content: str
    content_tokens: int


class DocumentChunksResponse(BaseModel):
    document_id: UUID
    file_name: str
    chunks: list[DocumentChunkOut]


class SourceCitation(BaseModel):
    """One retrieved chunk's metadata, sent to the FE so it can show
    the "Sources" accordion next to the assistant's answer."""

    document_id: UUID
    document_filename: str
    chunk_index: int
    distance: float
    preview: str  # first ~200 chars of the chunk
