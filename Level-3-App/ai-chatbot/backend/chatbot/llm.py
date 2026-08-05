"""OpenAI chat-completions streaming client (M5).

Mirrors embedder.py's singleton pattern but for chat instead of embeddings.
`stream_chat` is a thin async generator yielding text deltas as they arrive,
so the SSE endpoint can forward tokens to the browser in real time.

Kept vendor-specific details (the OpenAI SDK shape) behind one function so the
chat orchestrator stays provider-agnostic — swapping to another LLM later is a
change here only.

Usage/token accounting is done by the caller with tiktoken (deterministic and
testable) rather than parsing the fragile streamed usage chunk.
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from chatbot.config import get_settings
from openai import AsyncOpenAI

_LOGGER = logging.getLogger(__name__)

_SDK_MAX_RETRIES = 3
_SDK_TIMEOUT_SECONDS = 60.0

# OpenAI's free content-moderation model (multi-modal, text + image).
_MODERATION_MODEL = "omni-moderation-latest"

# Separate client from the embedder's: chat and embeddings have different
# latency/timeout profiles, and a streaming call holds the connection longer.
_CLIENT: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    """Lazy singleton; reads OPENAI_API_KEY from settings on first call."""
    global _CLIENT  # pylint: disable=global-statement
    if _CLIENT is None:
        settings = get_settings()
        # pydantic v2 Field default trips pylint/pylance type inference here.
        api_key = settings.openai_api_key.get_secret_value()  # type: ignore[attr-defined]  # pylint: disable=no-member
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is empty. Set it in .env before calling the LLM."
            )
        _CLIENT = AsyncOpenAI(
            api_key=api_key,
            max_retries=_SDK_MAX_RETRIES,
            timeout=_SDK_TIMEOUT_SECONDS,
        )
    return _CLIENT


async def reset_client() -> None:
    """Close + drop the cached client. Call from app shutdown or tests."""
    global _CLIENT  # pylint: disable=global-statement
    if _CLIENT is not None:
        await _CLIENT.close()
        _CLIENT = None


async def stream_chat(
    messages: list[dict[str, str]],
    *,
    model: str,
    temperature: float,
) -> AsyncIterator[str]:
    """Stream an assistant reply, yielding text deltas in arrival order.

    `messages` is the OpenAI chat format: [{"role": "system"|"user"|
    "assistant", "content": "..."}]. Empty deltas (role-only opening chunk,
    finish chunk) are skipped so the caller only sees real text.
    """
    client = _get_client()
    stream = await client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=messages,  # type: ignore[arg-type]
        stream=True,
    )
    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        text = getattr(delta, "content", None)
        if text:
            yield text


async def moderate(text: str) -> bool:
    """Return True when `text` is flagged by OpenAI's moderation endpoint.

    Uses the free `omni-moderation-latest` model. Fails OPEN: on any provider
    error the message is treated as allowed (returns False) and the failure is
    logged, so a moderation outage never takes chat down. Moderation is a
    defense-in-depth layer, not the only safety control.
    """
    try:
        client = _get_client()
        resp = await client.moderations.create(
            model=_MODERATION_MODEL, input=text
        )
        return bool(resp.results[0].flagged)
    except Exception:  # pylint: disable=broad-exception-caught
        _LOGGER.warning("Moderation check failed; allowing message (fail-open)", exc_info=True)
        return False
