"""M5 chat SSE tests.

The embedder, retriever, and LLM stream are mocked so tests are fast,
deterministic, and free (no OpenAI calls). We still hit the real Neon DB for
conversation/message/usage persistence and RLS. SSE frames are parsed off the
streamed response and DB rows are read back with a tenant-pinned session.
"""

from __future__ import annotations

import json
import uuid
from typing import AsyncIterator, Callable

import chatbot.chat as chat_module
import pytest
from chatbot.db import set_current_tenant
from chatbot.models import Conversation, Message, UsageEvent
from chatbot.retriever import RetrievedChunk
from httpx import AsyncClient
from sqlalchemy import select
from tests.conftest import TEST_SESSION, register_admin

_EMBEDDING_DIM = 1536


async def _fake_embed_one(_text: str) -> list[float]:
    return [0.01] * _EMBEDDING_DIM


def _one_chunk() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            content="Refunds are processed within 14 days.",
            distance=0.12,
            document_id=uuid.uuid4(),
            document_filename="policy.pdf",
            chunk_index=0,
        )
    ]


async def _fake_stream_chat(_messages, *, model, temperature) -> AsyncIterator[str]:
    _ = (model, temperature)
    for piece in ("Hello", " there"):
        yield piece


@pytest.fixture(autouse=True)
def _mock_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the network seams the chat orchestrator calls."""
    monkeypatch.setattr(chat_module, "embed_one", _fake_embed_one)
    monkeypatch.setattr(chat_module, "stream_chat", _fake_stream_chat)
    monkeypatch.setattr(
        chat_module, "retrieve", lambda *a, **k: _async_return(_one_chunk())
    )


def _async_return(value):
    async def _coro():
        return value

    return _coro()


async def _open_session(
    client: AsyncClient, make_email: Callable[[], str]
) -> dict[str, str]:
    """Register admin, create a bot, open a widget session. Returns a dict
    with token headers + tenant_id + bot_id + session_id."""
    auth = await register_admin(client, make_email())
    me = (await client.get("/api/auth/me", headers=auth)).json()
    tenant_id = me["admin"]["tenant_id"]
    bot_id = (
        await client.post("/api/bots", headers=auth, json={"name": "Support"})
    ).json()["id"]
    session = (
        await client.post(
            "/api/widget/session",
            json={"bot_id": bot_id, "tenant_id": tenant_id},
        )
    ).json()
    return {
        "auth": auth,
        "headers": {"Authorization": f"Bearer {session['access_token']}"},
        "tenant_id": tenant_id,
        "bot_id": bot_id,
        "session_id": session["session_id"],
    }


async def _stream_chat_events(
    client: AsyncClient,
    headers: dict[str, str],
    body: dict,
) -> list[tuple[str, dict]]:
    """POST to the SSE endpoint and parse the frames into (event, data)."""
    events: list[tuple[str, dict]] = []
    async with client.stream(
        "POST", "/api/widget/chat", headers=headers, json=body
    ) as resp:
        assert resp.status_code == 200, await resp.aread()
        cur_event: str | None = None
        async for line in resp.aiter_lines():
            if line.startswith("event: "):
                cur_event = line[len("event: ") :]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: ") :])
                assert cur_event is not None
                events.append((cur_event, data))
                cur_event = None
    return events


async def _messages(tenant_id: str, conversation_id: str) -> list[Message]:
    async with TEST_SESSION() as session:
        await set_current_tenant(session, uuid.UUID(tenant_id))
        rows = (
            (
                await session.execute(
                    select(Message)
                    .where(Message.conversation_id == uuid.UUID(conversation_id))
                    .order_by(Message.created_at)
                )
            )
            .scalars()
            .all()
        )
        return list(rows)


@pytest.mark.asyncio
async def test_chat_streams_and_persists(
    client: AsyncClient, make_email: Callable[[], str]
) -> None:
    ctx = await _open_session(client, make_email)
    events = await _stream_chat_events(
        client, ctx["headers"], {"message": "How long for a refund?"}
    )

    kinds = [e for e, _ in events]
    assert kinds[0] == "meta"
    assert "sources" in kinds
    assert kinds[-1] == "done"

    meta = next(d for e, d in events if e == "meta")
    sources = next(d for e, d in events if e == "sources")
    deltas = [d["text"] for e, d in events if e == "delta"]
    done = next(d for e, d in events if e == "done")

    assert len(sources) == 1
    assert "".join(deltas) == "Hello there"
    assert done["tokens_out"] > 0

    msgs = await _messages(ctx["tenant_id"], meta["conversation_id"])
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert msgs[1].content == "Hello there"
    assert msgs[1].status == "completed"
    assert msgs[1].sources and len(msgs[1].sources) == 1


@pytest.mark.asyncio
async def test_chat_records_usage(
    client: AsyncClient, make_email: Callable[[], str]
) -> None:
    ctx = await _open_session(client, make_email)
    await _stream_chat_events(client, ctx["headers"], {"message": "Hi"})

    async with TEST_SESSION() as session:
        await set_current_tenant(session, uuid.UUID(ctx["tenant_id"]))
        # Filter by tenant_id explicitly: the app DB role has BYPASSRLS, so the
        # RLS GUC does not scope this query. Without the filter the test would
        # see chat usage from every other tenant in the shared dev database.
        usage = (
            (
                await session.execute(
                    select(UsageEvent).where(
                        UsageEvent.event_type == "chat",
                        UsageEvent.tenant_id == uuid.UUID(ctx["tenant_id"]),
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(usage) == 1
    assert usage[0].tokens_out > 0


@pytest.mark.asyncio
async def test_chat_continues_conversation(
    client: AsyncClient, make_email: Callable[[], str]
) -> None:
    ctx = await _open_session(client, make_email)
    first = await _stream_chat_events(client, ctx["headers"], {"message": "first"})
    conv_id = next(d for e, d in first if e == "meta")["conversation_id"]

    second = await _stream_chat_events(
        client,
        ctx["headers"],
        {"message": "second", "conversation_id": conv_id},
    )
    assert next(d for e, d in second if e == "meta")["conversation_id"] == conv_id

    msgs = await _messages(ctx["tenant_id"], conv_id)
    assert [m.role for m in msgs] == ["user", "assistant", "user", "assistant"]


@pytest.mark.asyncio
async def test_chat_no_context_still_answers(
    client: AsyncClient, make_email: Callable[[], str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(chat_module, "retrieve", lambda *a, **k: _async_return([]))
    ctx = await _open_session(client, make_email)
    events = await _stream_chat_events(
        client, ctx["headers"], {"message": "unrelated question"}
    )

    sources = next(d for e, d in events if e == "sources")
    assert sources == []
    assert [e for e, _ in events][-1] == "done"


@pytest.mark.asyncio
async def test_chat_preview_skips_usage(
    client: AsyncClient, make_email: Callable[[], str]
) -> None:
    auth = await register_admin(client, make_email())
    me = (await client.get("/api/auth/me", headers=auth)).json()
    tenant_id = me["admin"]["tenant_id"]
    bot_id = (
        await client.post("/api/bots", headers=auth, json={"name": "Support"})
    ).json()["id"]
    preview = (
        await client.post(f"/api/bots/{bot_id}/preview-session", headers=auth)
    ).json()
    headers = {"Authorization": f"Bearer {preview['access_token']}"}

    events = await _stream_chat_events(client, headers, {"message": "hi"})
    assert [e for e, _ in events][-1] == "done"

    async with TEST_SESSION() as session:
        await set_current_tenant(session, uuid.UUID(tenant_id))
        # Filter by tenant_id explicitly: the app DB role has BYPASSRLS, so the
        # RLS GUC does not scope these queries against the shared dev database.
        usage = (
            (
                await session.execute(
                    select(UsageEvent).where(
                        UsageEvent.event_type == "chat",
                        UsageEvent.tenant_id == uuid.UUID(tenant_id),
                    )
                )
            )
            .scalars()
            .all()
        )
        conv = (
            (
                await session.execute(
                    select(Conversation).where(
                        Conversation.tenant_id == uuid.UUID(tenant_id)
                    )
                )
            )
            .scalars()
            .all()
        )
    assert usage == []
    assert conv and conv[0].is_preview is True


@pytest.mark.asyncio
async def test_chat_requires_auth(client: AsyncClient) -> None:
    resp = await client.post("/api/widget/chat", json={"message": "hi"})
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_chat_unknown_conversation_404(
    client: AsyncClient, make_email: Callable[[], str]
) -> None:
    ctx = await _open_session(client, make_email)
    resp = await client.post(
        "/api/widget/chat",
        headers=ctx["headers"],
        json={"message": "hi", "conversation_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_chat_empty_message_422(
    client: AsyncClient, make_email: Callable[[], str]
) -> None:
    ctx = await _open_session(client, make_email)
    resp = await client.post(
        "/api/widget/chat", headers=ctx["headers"], json={"message": ""}
    )
    assert resp.status_code == 422, resp.text
