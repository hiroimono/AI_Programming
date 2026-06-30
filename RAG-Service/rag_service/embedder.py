"""OpenAI embedding client.

Wraps `AsyncOpenAI` so the rest of the service stays vendor-agnostic
and async-friendly. The embedder is used in two places:
  - Ingestion: chunker outputs N chunks → embed_batch(N texts) → store
    the resulting vectors next to each chunk row.
  - Retrieval: a user query gets embed_one()'d, then pgvector finds
    the nearest chunks by cosine distance.

Why batch? The OpenAI embeddings endpoint accepts up to 2048 inputs
per request. Submitting one-at-a-time would be ~100x slower and burn
the per-minute request quota for nothing.

Why a singleton client? `AsyncOpenAI` holds an httpx connection pool;
constructing a new one per call leaks sockets and re-does TLS handshakes.
"""

from __future__ import annotations

from openai import AsyncOpenAI

from rag_service.config import get_settings

# How many texts to send in one /embeddings call. OpenAI allows up to
# 2048 inputs but each one counts against the per-minute token quota;
# 100 keeps memory + retry blast-radius small while still ~100x faster
# than one-at-a-time.
EMBED_BATCH_SIZE = 100

# Hard cap per individual input. text-embedding-3-small accepts up to
# 8192 tokens per input; our chunker emits ~500 so this is defensive.
EMBED_MAX_INPUT_TOKENS = 8000

# SDK-level retry/backoff. Handles 429 (rate limit) and 5xx automatically
# with exponential backoff. We set it once on the singleton client.
_SDK_MAX_RETRIES = 3
_SDK_TIMEOUT_SECONDS = 30.0

_CLIENT: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    """Lazy singleton; reads OPENAI_API_KEY from settings on first call."""
    global _CLIENT  # pylint: disable=global-statement
    if _CLIENT is None:
        settings = get_settings()
        # pydantic v2 Field default trips pylint/pylance Type inference here.
        api_key = settings.openai_api_key.get_secret_value()  # type: ignore[attr-defined]  # pylint: disable=no-member
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is empty. Set it in .env before calling embedder."
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


async def embed_one(text: str) -> list[float]:
    """Embed a single string (typically a user query).

    Returns a 1536-dim float vector matching the DB's Vector(1536) column.
    Raises ValueError on empty input — callers should never pass blank.
    """
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text")
    result = await embed_batch([text])
    return result[0]


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed N texts; preserves input order.

    Splits into EMBED_BATCH_SIZE chunks under the hood, calls the API
    once per batch, then re-concatenates. The OpenAI SDK guarantees
    response.data is returned in the same order as the request input,
    so order is safe.
    """
    if not texts:
        return []

    settings = get_settings()
    client = _get_client()
    model = settings.openai_embedding_model
    expected_dim = settings.openai_embedding_dim

    out: list[list[float]] = []
    for batch_start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[batch_start : batch_start + EMBED_BATCH_SIZE]
        response = await client.embeddings.create(model=model, input=batch)

        # Defensive: surface a dim mismatch early. If we ever change
        # openai_embedding_dim in config without re-running migrations,
        # this catches it before silently writing the wrong-size vectors.
        for item in response.data:
            vec = item.embedding
            if len(vec) != expected_dim:
                raise RuntimeError(
                    f"Embedding dim mismatch: got {len(vec)}, "
                    f"expected {expected_dim} (model={model!r})"
                )
            out.append(vec)

    return out
