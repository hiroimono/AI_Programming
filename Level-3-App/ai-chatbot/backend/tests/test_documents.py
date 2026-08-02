"""Document upload/list/get/delete tests (M3 — RAG training).

The embedder is monkeypatched so no real OpenAI call is made: ingestion
is exercised end-to-end (parse -> chunk -> fake-embed -> store) against
the live Neon dev DB, but deterministically and for free.

Every test registers a fresh tenant (email prefixed for autouse cleanup),
so runs are isolated and self-cleaning.
"""

from __future__ import annotations

from typing import Callable

import pytest
import pytest_asyncio
from chatbot.models.document import EMBEDDING_DIM
from httpx import AsyncClient
from tests.conftest import register_admin

# A text long enough to yield at least one chunk (>= MIN_CHUNK_TOKENS).
_SAMPLE_TEXT = (
    b"This is a training document about the company refund policy. "
    b"Customers may request a refund within 30 days of purchase. "
) * 20


@pytest_asyncio.fixture(autouse=True)
def _mock_embedder(monkeypatch) -> None:
    """Replace the OpenAI batch embedder with a deterministic stub."""

    async def _fake_embed_batch(texts: list[str]) -> list[list[float]]:
        return [[0.01] * EMBEDDING_DIM for _ in texts]

    monkeypatch.setattr("chatbot.pipeline.embed_batch", _fake_embed_batch)


async def _create_bot(client: AsyncClient, auth: dict[str, str]) -> str:
    resp = await client.post("/api/bots", json={"name": "Support Bot"}, headers=auth)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _txt_upload(content: bytes = _SAMPLE_TEXT, name: str = "policy.txt") -> dict:
    return {"file": (name, content, "text/plain")}


@pytest.mark.asyncio
async def test_upload_creates_document_and_chunks(
    client: AsyncClient, admin_auth: dict[str, str]
) -> None:
    bot_id = await _create_bot(client, admin_auth)
    resp = await client.post(
        f"/api/bots/{bot_id}/documents", files=_txt_upload(), headers=admin_auth
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "ready"
    assert body["file_type"] == "txt"
    assert body["chunk_count"] >= 1
    assert body["error_message"] is None


@pytest.mark.asyncio
async def test_list_documents(client: AsyncClient, admin_auth: dict[str, str]) -> None:
    bot_id = await _create_bot(client, admin_auth)
    await client.post(
        f"/api/bots/{bot_id}/documents", files=_txt_upload(), headers=admin_auth
    )
    resp = await client.get(f"/api/bots/{bot_id}/documents", headers=admin_auth)
    assert resp.status_code == 200
    docs = resp.json()
    assert len(docs) == 1
    assert docs[0]["file_name"] == "policy.txt"


@pytest.mark.asyncio
async def test_get_document_and_unknown_404(
    client: AsyncClient, admin_auth: dict[str, str]
) -> None:
    bot_id = await _create_bot(client, admin_auth)
    created = await client.post(
        f"/api/bots/{bot_id}/documents", files=_txt_upload(), headers=admin_auth
    )
    doc_id = created.json()["id"]

    ok = await client.get(f"/api/bots/{bot_id}/documents/{doc_id}", headers=admin_auth)
    assert ok.status_code == 200
    assert ok.json()["id"] == doc_id

    missing = await client.get(
        f"/api/bots/{bot_id}/documents/00000000-0000-0000-0000-000000000000",
        headers=admin_auth,
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_upload_unsupported_type_415(
    client: AsyncClient, admin_auth: dict[str, str]
) -> None:
    bot_id = await _create_bot(client, admin_auth)
    resp = await client.post(
        f"/api/bots/{bot_id}/documents",
        files={"file": ("malware.exe", b"MZ\x90\x00", "application/octet-stream")},
        headers=admin_auth,
    )
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_upload_empty_file_422(
    client: AsyncClient, admin_auth: dict[str, str]
) -> None:
    bot_id = await _create_bot(client, admin_auth)
    resp = await client.post(
        f"/api/bots/{bot_id}/documents",
        files=_txt_upload(content=b"", name="empty.txt"),
        headers=admin_auth,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_document_soft(
    client: AsyncClient, admin_auth: dict[str, str]
) -> None:
    bot_id = await _create_bot(client, admin_auth)
    created = await client.post(
        f"/api/bots/{bot_id}/documents", files=_txt_upload(), headers=admin_auth
    )
    doc_id = created.json()["id"]

    deleted = await client.delete(
        f"/api/bots/{bot_id}/documents/{doc_id}", headers=admin_auth
    )
    assert deleted.status_code == 204

    # Soft-deleted -> gone from GET and list.
    assert (
        await client.get(f"/api/bots/{bot_id}/documents/{doc_id}", headers=admin_auth)
    ).status_code == 404
    listed = await client.get(f"/api/bots/{bot_id}/documents", headers=admin_auth)
    assert listed.json() == []

    # Second delete is a 404 (already gone).
    assert (
        await client.delete(
            f"/api/bots/{bot_id}/documents/{doc_id}", headers=admin_auth
        )
    ).status_code == 404


@pytest.mark.asyncio
async def test_upload_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/bots/00000000-0000-0000-0000-000000000000/documents",
        files=_txt_upload(),
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_upload_unknown_bot_404(
    client: AsyncClient, admin_auth: dict[str, str]
) -> None:
    resp = await client.post(
        "/api/bots/00000000-0000-0000-0000-000000000000/documents",
        files=_txt_upload(),
        headers=admin_auth,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_tenant_isolation(
    client: AsyncClient, make_email: Callable[[], str]
) -> None:
    # Tenant A uploads a document to A's bot.
    auth_a = await register_admin(client, make_email())
    bot_a = await _create_bot(client, auth_a)
    await client.post(
        f"/api/bots/{bot_a}/documents", files=_txt_upload(), headers=auth_a
    )

    # Tenant B cannot see A's bot or its documents (RLS -> 404 on the bot).
    auth_b = await register_admin(client, make_email())
    resp = await client.get(f"/api/bots/{bot_a}/documents", headers=auth_b)
    assert resp.status_code == 404
