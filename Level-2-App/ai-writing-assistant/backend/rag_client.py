"""rag_client.py - thin httpx client for the central rag-service.

Every call mints a fresh, short-lived (60s) internal HS256 JWT signed
with the secret shared with rag-service. The token carries the
end-user's id (from the Gateway JWT) plus the app_id
(`level-2-writer`) and an optional conversation id.

This module is intentionally stateless. It exposes one client class
plus tiny dataclasses for the wire response shapes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import unquote
from uuid import UUID

import httpx
import jwt as pyjwt
from config import settings
from fastapi import HTTPException, status

# Each minted token lives 60 seconds. Plenty for a single round-trip,
# small enough to limit blast radius if logs leak.
_TOKEN_TTL_SECONDS = 60
# How long to wait for rag-service per call. Upload/embed can be slow
# on big files; retrieve is fast. 60s is a generous cap.
_HTTP_TIMEOUT_SECONDS = 60.0


def _parse_disposition_filename(disposition: str) -> str:
    """Extract a usable filename from a Content-Disposition header.

    Prefers the RFC 5987 `filename*=UTF-8''...` form (unicode-safe) and
    falls back to the legacy `filename="..."` quoted-ascii form.
    """
    if not disposition:
        return "document"
    # RFC 5987: filename*=UTF-8''<percent-encoded>
    marker = "filename*=UTF-8''"
    if marker in disposition:
        encoded = disposition.split(marker, 1)[1].split(";", 1)[0].strip()
        try:
            return unquote(encoded)
        except (ValueError, UnicodeDecodeError):
            pass
    if 'filename="' in disposition:
        return disposition.split('filename="', 1)[1].split('"', 1)[0]
    return "document"


@dataclass
class RagDocument:
    """Mirror of rag-service's DocumentItem response (shape, not class)."""

    id: str
    file_name: str
    file_type: str
    mime_type: str | None
    file_size_bytes: int
    status: str
    chunk_count: int
    created_at: str
    error_message: str | None


@dataclass
class RetrievedChunk:
    """Mirror of rag-service's RetrievedChunkOut."""

    content: str
    distance: float
    document_id: str
    document_filename: str
    chunk_index: int
    metadata: dict[str, Any]


class RagClient:
    """Wraps rag-service's HTTP API.

    A single instance is created at process startup and shared across
    requests. httpx.AsyncClient handles connection pooling.
    """

    def __init__(self, base_url: str, secret: str, app_id: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._secret = secret
        self._app_id = app_id
        self._http: httpx.AsyncClient | None = None

    async def startup(self) -> None:
        """Create the underlying connection pool. Called from FastAPI lifespan."""
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=_HTTP_TIMEOUT_SECONDS,
        )

    async def shutdown(self) -> None:
        """Close the pool. Called from FastAPI lifespan."""
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    # ────────────────────────────────────────────────────────────────
    # Internal helpers
    # ────────────────────────────────────────────────────────────────

    def _mint_token(self, user_id: str, conversation_id: UUID | None) -> str:
        """Build a short-lived HS256 token rag-service will accept."""
        now = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "iss": "level-2-writer",
            "sub": user_id,
            "app_id": self._app_id,
            "iat": now,
            "exp": now + timedelta(seconds=_TOKEN_TTL_SECONDS),
        }
        if conversation_id is not None:
            payload["conversation_id"] = str(conversation_id)
        return pyjwt.encode(payload, self._secret, algorithm="HS256")

    def _headers(self, user_id: str, conversation_id: UUID | None) -> dict[str, str]:
        token = self._mint_token(user_id, conversation_id)
        return {"Authorization": f"Bearer {token}"}

    def _require_client(self) -> httpx.AsyncClient:
        if self._http is None:
            raise RuntimeError("RagClient.startup() was not called")
        return self._http

    @staticmethod
    def _bubble(response: httpx.Response) -> None:
        """Translate rag-service errors into the same HTTPException so the
        Level-2 BE returns matching status codes to the frontend."""
        if response.is_success:
            return
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text or f"rag-service error {response.status_code}"
        raise HTTPException(status_code=response.status_code, detail=detail)

    # ────────────────────────────────────────────────────────────────
    # Documents
    # ────────────────────────────────────────────────────────────────

    async def upload_document(
        self,
        *,
        user_id: str,
        conversation_id: UUID | None,
        filename: str,
        content: bytes,
        mime_type: str | None,
    ) -> dict[str, Any]:
        """POST a file to rag-service. Returns ingest response dict."""
        client = self._require_client()
        files = {"file": (filename, content, mime_type or "application/octet-stream")}
        data: dict[str, str] = {}
        if conversation_id is not None:
            data["conversation_id"] = str(conversation_id)
        response = await client.post(
            "/api/documents",
            headers=self._headers(user_id, conversation_id),
            files=files,
            data=data,
        )
        self._bubble(response)
        return response.json()

    async def list_documents(
        self,
        *,
        user_id: str,
        conversation_id: UUID | None,
    ) -> list[RagDocument]:
        """GET /api/documents. Conversation filter is optional."""
        client = self._require_client()
        params: dict[str, str] = {}
        if conversation_id is not None:
            params["conversation_id"] = str(conversation_id)
        response = await client.get(
            "/api/documents",
            headers=self._headers(user_id, conversation_id),
            params=params,
        )
        self._bubble(response)
        return [RagDocument(**d) for d in response.json().get("documents", [])]

    async def delete_document(
        self,
        *,
        user_id: str,
        document_id: UUID,
    ) -> None:
        """DELETE /api/documents/{id}. 404 bubbles up unchanged."""
        client = self._require_client()
        response = await client.delete(
            f"/api/documents/{document_id}",
            headers=self._headers(user_id, None),
        )
        self._bubble(response)

    async def get_document_chunks(
        self,
        *,
        user_id: str,
        document_id: UUID,
    ) -> dict:
        """GET /api/documents/{id}/chunks. Returns the raw envelope
        (document_id, file_name, chunks) for the BE to forward as-is."""
        client = self._require_client()
        response = await client.get(
            f"/api/documents/{document_id}/chunks",
            headers=self._headers(user_id, None),
        )
        self._bubble(response)
        return response.json()

    async def get_document_file(
        self,
        *,
        user_id: str,
        document_id: UUID,
    ) -> tuple[bytes, str, str]:
        """GET /api/documents/{id}/file. Returns (bytes, content_type, filename).

        Used by the BE to stream the original upload back to the browser
        without persisting it locally. Filename is parsed from
        Content-Disposition (RFC 5987 utf-8 hint preferred over the
        ASCII fallback when present)."""
        client = self._require_client()
        response = await client.get(
            f"/api/documents/{document_id}/file",
            headers=self._headers(user_id, None),
        )
        self._bubble(response)
        content_type = response.headers.get("content-type", "application/octet-stream")
        disposition = response.headers.get("content-disposition", "")
        filename = _parse_disposition_filename(disposition)
        return response.content, content_type, filename

    # ────────────────────────────────────────────────────────────────
    # Retrieval
    # ────────────────────────────────────────────────────────────────

    async def retrieve(
        self,
        *,
        user_id: str,
        conversation_id: UUID | None,
        query: str,
        k: int = 4,
        max_distance: float = 0.4,
    ) -> list[RetrievedChunk]:
        """POST /api/retrieve. Returns top-k chunks under the distance ceiling."""
        client = self._require_client()
        response = await client.post(
            "/api/retrieve",
            headers=self._headers(user_id, conversation_id),
            json={"query": query, "k": k, "max_distance": max_distance},
        )
        self._bubble(response)
        return [RetrievedChunk(**c) for c in response.json().get("chunks", [])]


# Singleton, configured at import time. Lifespan hooks must call startup/shutdown.
_CLIENT: RagClient | None = None


def get_rag_client() -> RagClient:
    """FastAPI dependency / module access point.

    Returns the singleton if it was started, otherwise raises 503 so
    auth-required endpoints can fail cleanly when rag-service config
    is missing.
    """
    global _CLIENT  # pylint: disable=global-statement
    if _CLIENT is None:
        if not settings.rag_enabled():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="RAG features are not configured on this server",
            )
        _CLIENT = RagClient(
            base_url=settings.rag_service_url,
            secret=settings.rag_internal_jwt_secret,
            app_id=settings.rag_app_id,
        )
    return _CLIENT


async def startup_rag_client() -> None:
    """Initialize the client pool. Idempotent."""
    if not settings.rag_enabled():
        return
    client = get_rag_client()
    await client.startup()


async def shutdown_rag_client() -> None:
    """Close the client pool. Idempotent."""
    global _CLIENT  # pylint: disable=global-statement
    if _CLIENT is not None:
        await _CLIENT.shutdown()
        _CLIENT = None
