"""Chat-turn orchestration (M5): retrieve -> ground -> stream -> persist.

`run_chat_turn` is an async generator that yields SSE event dicts as the turn
progresses (meta -> sources -> many delta -> done | error). The SSE router
formats each dict onto the wire; keeping the wire format out of here makes the
orchestration unit-testable without an HTTP client.

Design notes:
  - Own sessions (like the ingestion pipeline): this generator opens its own
    `session_factory()` blocks and RE-PINS the RLS tenant in each, because the
    request-scoped session may be torn down mid-stream and the RLS GUC is
    transaction-local (cleared on commit).
  - Grounding guard: the retriever returns [] when nothing is close enough;
    we then stream a normal reply but the system prompt tells the model to
    admit it lacks the info instead of hallucinating.
  - Input moderation (M8): each user message is screened by OpenAI's free
    moderation endpoint before retrieval/LLM. A flagged turn is answered with
    a canned refusal (persisted for audit, status "blocked") and never calls
    the model.
  - Preview turns (is_preview) skip the UsageEvent so admin testing never
    counts toward quota/analytics.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import AsyncIterator, Optional
from uuid import UUID

from chatbot.chunker import count_tokens
from chatbot.config import get_settings
from chatbot.db import session_factory, set_current_tenant
from chatbot.embedder import embed_one
from chatbot.llm import moderate, stream_chat
from chatbot.models import BotConfig, Conversation, Message, UsageEvent
from chatbot.retriever import RetrievedChunk, retrieve
from sqlalchemy import select, update

# How many prior messages to replay as chat history. Keeps the prompt bounded.
HISTORY_LIMIT = 10

# Conversation title = first user message, truncated to fit the column.
_TITLE_MAX_LEN = 200

_DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant embedded on a company's website. Answer the "
    "user's questions using the provided context. If the answer is not in the "
    "context, say you don't have that information rather than guessing."
)


async def _is_flagged(text: str) -> bool:
    """Return True when the input should be blocked by content moderation.

    Honors settings.moderation_enabled so moderation can be turned off per
    environment (and in tests) without touching the call site.
    """
    if not get_settings().moderation_enabled:
        return False
    return await moderate(text)


def _build_context_block(chunks: list[RetrievedChunk]) -> str:
    """Render retrieved chunks into a context block for the system prompt."""
    parts = [
        f"[{i + 1}] (source: {c.document_filename})\n{c.content}"
        for i, c in enumerate(chunks)
    ]
    return "\n\n".join(parts)


def _sources_payload(chunks: list[RetrievedChunk]) -> list[dict]:
    """Browser-safe citation list attached to the assistant message + SSE."""
    return [
        {
            "document_id": str(c.document_id),
            "file_name": c.document_filename,
            "chunk_index": c.chunk_index,
            "distance": round(c.distance, 4),
        }
        for c in chunks
    ]


async def _open_turn(
    *,
    tenant_id: UUID,
    bot_id: UUID,
    session_id: str,
    is_preview: bool,
    user_message: str,
    conversation_id: Optional[UUID],
) -> tuple[UUID, UUID, list[dict[str, str]], str, str, float]:
    """First write block: load/create the conversation, record the user turn
    and an empty streaming assistant turn, and read back the config + history.

    Returns (conversation_id, assistant_message_id, history, system_prompt,
    model, temperature).
    """
    async with session_factory() as session:
        await set_current_tenant(session, tenant_id)

        if conversation_id is not None:
            conversation = (
                await session.execute(
                    select(Conversation).where(
                        Conversation.id == conversation_id,
                        Conversation.session_id == session_id,
                    )
                )
            ).scalar_one_or_none()
            if conversation is None:
                raise ValueError("conversation not found for this session")
        else:
            conversation = Conversation(
                tenant_id=tenant_id,
                bot_id=bot_id,
                session_id=session_id,
                is_preview=is_preview,
                title=user_message[:_TITLE_MAX_LEN],
                status="active",
            )
            session.add(conversation)
            await session.flush()

        conv_id = conversation.id

        # History = prior turns only (before we add the current pair).
        history_rows = (
            await session.execute(
                select(Message.role, Message.content)
                .where(Message.conversation_id == conv_id)
                .order_by(Message.created_at.desc())
                .limit(HISTORY_LIMIT)
            )
        ).all()
        history = [
            {"role": role, "content": content}
            for role, content in reversed(history_rows)
        ]

        # Explicit, strictly increasing timestamps: user then assistant are
        # inserted in the SAME transaction, so Postgres now() (transaction
        # time) would tie them and ORDER BY created_at would be ambiguous.
        # A 1ms gap keeps history replay and display order deterministic.
        now = datetime.now(timezone.utc)
        session.add(
            Message(
                tenant_id=tenant_id,
                conversation_id=conv_id,
                role="user",
                content=user_message,
                status="completed",
                created_at=now,
            )
        )
        assistant = Message(
            tenant_id=tenant_id,
            conversation_id=conv_id,
            role="assistant",
            content="",
            status="streaming",
            created_at=now + timedelta(milliseconds=1),
        )
        session.add(assistant)
        await session.flush()
        assistant_id = assistant.id
        config = (
            await session.execute(select(BotConfig).where(BotConfig.bot_id == bot_id))
        ).scalar_one_or_none()

        settings = get_settings()
        system_prompt = (
            config.system_prompt
            if config and config.system_prompt
            else _DEFAULT_SYSTEM_PROMPT
        )
        model = config.model if config else settings.openai_chat_model
        temperature = config.temperature if config else 0.2

        await session.commit()

    return conv_id, assistant_id, history, system_prompt, model, temperature


async def _finalize_turn(
    *,
    tenant_id: UUID,
    bot_id: UUID,
    assistant_id: UUID,
    answer: str,
    sources: list[dict],
    status: str,
    is_preview: bool,
    model: str,
    tokens_in: int,
    tokens_out: int,
) -> None:
    """Final write block: persist the assistant answer + citations, and (for
    non-preview turns) a chat UsageEvent."""
    async with session_factory() as session:
        await set_current_tenant(session, tenant_id)
        await session.execute(
            update(Message)
            .where(Message.id == assistant_id)
            .values(content=answer, sources=sources or None, status=status)
        )
        if not is_preview and status == "completed":
            session.add(
                UsageEvent(
                    tenant_id=tenant_id,
                    bot_id=bot_id,
                    event_type="chat",
                    model=model,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                )
            )
        await session.commit()


async def run_chat_turn(
    *,
    tenant_id: UUID,
    bot_id: UUID,
    session_id: str,
    is_preview: bool,
    user_message: str,
    conversation_id: Optional[UUID] = None,
) -> AsyncIterator[dict]:
    """Drive one chat turn, yielding SSE event dicts as it progresses."""
    conv_id, assistant_id, history, system_prompt, model, temperature = (
        await _open_turn(
            tenant_id=tenant_id,
            bot_id=bot_id,
            session_id=session_id,
            is_preview=is_preview,
            user_message=user_message,
            conversation_id=conversation_id,
        )
    )

    yield {
        "event": "meta",
        "data": {"conversation_id": str(conv_id), "message_id": str(assistant_id)},
    }

    # Input moderation gate (M8): block disallowed content before it reaches
    # retrieval or the LLM. Stream a canned refusal and persist it as the
    # assistant answer (audit trail, status "blocked") without a model call.
    if await _is_flagged(user_message):
        refusal = get_settings().moderation_refusal_message
        yield {"event": "sources", "data": []}
        yield {"event": "delta", "data": {"text": refusal}}
        await _finalize_turn(
            tenant_id=tenant_id,
            bot_id=bot_id,
            assistant_id=assistant_id,
            answer=refusal,
            sources=[],
            status="blocked",
            is_preview=is_preview,
            model=model,
            tokens_in=0,
            tokens_out=0,
        )
        yield {
            "event": "done",
            "data": {
                "message_id": str(assistant_id),
                "tokens_in": 0,
                "tokens_out": 0,
            },
        }
        return

    answer_parts: list[str] = []
    try:
        # Retrieve grounding context (embed query -> cosine top-k).
        query_vector = await embed_one(user_message)
        async with session_factory() as session:
            await set_current_tenant(session, tenant_id)
            chunks = await retrieve(session, bot_id=bot_id, query_vector=query_vector)

        sources = _sources_payload(chunks)
        yield {"event": "sources", "data": sources}

        # Build the chat prompt: system(+context) -> history -> user turn.
        system_content = system_prompt
        if chunks:
            system_content += "\n\nContext:\n" + _build_context_block(chunks)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_content},
            *history,
            {"role": "user", "content": user_message},
        ]

        async for delta in stream_chat(messages, model=model, temperature=temperature):
            answer_parts.append(delta)
            yield {"event": "delta", "data": {"text": delta}}

        answer = "".join(answer_parts)
        tokens_in = sum(count_tokens(m["content"]) for m in messages)
        tokens_out = count_tokens(answer)

        await _finalize_turn(
            tenant_id=tenant_id,
            bot_id=bot_id,
            assistant_id=assistant_id,
            answer=answer,
            sources=sources,
            status="completed",
            is_preview=is_preview,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )

        yield {
            "event": "done",
            "data": {
                "message_id": str(assistant_id),
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
            },
        }

    except Exception as exc:  # pylint: disable=broad-exception-caught
        # Persist whatever streamed so far and mark the turn aborted.
        await _finalize_turn(
            tenant_id=tenant_id,
            bot_id=bot_id,
            assistant_id=assistant_id,
            answer="".join(answer_parts),
            sources=[],
            status="aborted",
            is_preview=is_preview,
            model=model,
            tokens_in=0,
            tokens_out=0,
        )
        yield {"event": "error", "data": {"message": str(exc)}}
