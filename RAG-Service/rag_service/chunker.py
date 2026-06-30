"""Token-aware text chunker for RAG ingestion.

A document's full_text (output of `parsers/`) gets split into ~500-token
windows with 50-token overlap. We count tokens with tiktoken's
`cl100k_base` encoding — the same tokenizer GPT-4o uses — so chunk
boundaries align with what the LLM will eventually see.

Why a sliding window (not sentence- or paragraph-level)?
  - Deterministic: same input → same chunks (idempotent re-ingestion).
  - Predictable cost: every chunk ≤ chunk_size tokens, so the embedding
    API never rejects a batch element for being too long.
  - Overlap (CHUNK_OVERLAP) gives the next chunk enough leading context
    that a sentence cut in half by the window still appears whole in
    one of the two neighbors → retrieval doesn't lose facts at borders.

Why not semantic chunking? Slower, non-deterministic, and the win
disappears once retrieval is good. Defer until needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import tiktoken

# Pinned encoding — must match the model family used by embedder/LLM.
# cl100k_base is shared by text-embedding-3-small and GPT-4o.
_ENCODING_NAME = "cl100k_base"

# Tunables. Numbers chosen for the strategy doc's target: dense retrieval
# over short user-uploaded documents (PDFs, DOCX, XLSX, text snippets).
CHUNK_SIZE_TOKENS = 500
CHUNK_OVERLAP_TOKENS = 50
MIN_CHUNK_TOKENS = 20  # drop trailing dust like "Page 12 of 12"

# Module-level encoder is safe to share; tiktoken Encoding is thread-safe
# for encode/decode calls (immutable BPE tables).
_ENCODER = tiktoken.get_encoding(_ENCODING_NAME)


@dataclass
class Chunk:
    """One unit of text that will be embedded and stored as a row.

    `chunk_index` is the per-document ordinal (0, 1, 2, ...). The DB
    has UNIQUE(document_id, chunk_index) so a retry of ingestion will
    deterministically overwrite the same rows instead of duplicating.
    """

    chunk_index: int
    content: str
    content_tokens: int
    metadata: dict[str, Any] = field(default_factory=dict)


def count_tokens(text: str) -> int:
    """Public helper: how many tokens does this text consume?"""
    return len(_ENCODER.encode(text))


def chunk_text(
    text: str,
    *,
    chunk_size: int = CHUNK_SIZE_TOKENS,
    overlap: int = CHUNK_OVERLAP_TOKENS,
    base_metadata: dict[str, Any] | None = None,
) -> list[Chunk]:
    """Split `text` into overlapping token windows.

    Returns an empty list if `text` is empty or shorter than
    MIN_CHUNK_TOKENS (avoids polluting the index with near-empty rows).

    Algorithm:
      1. Encode the full text to a token list once.
      2. Slide a window of `chunk_size` across, stepping by
         (chunk_size - overlap) each time.
      3. Decode each window back to text.

    Decoding round-trip is lossless for cl100k_base, so users see the
    original characters back.
    """
    if not text or not text.strip():
        return []
    if chunk_size <= overlap:
        raise ValueError(
            f"chunk_size ({chunk_size}) must be greater than overlap ({overlap})"
        )

    token_ids = _ENCODER.encode(text)
    if len(token_ids) < MIN_CHUNK_TOKENS:
        return []

    step = chunk_size - overlap
    chunks: list[Chunk] = []
    chunk_index = 0
    start = 0
    total = len(token_ids)

    while start < total:
        end = min(start + chunk_size, total)
        window_ids = token_ids[start:end]

        # Tail guard: when the very last window is mostly overlap with
        # the previous chunk, the new tokens it contributes might be
        # below MIN_CHUNK_TOKENS. Skip it — its content already lives
        # in the previous chunk.
        if start > 0 and (end - start) < MIN_CHUNK_TOKENS:
            break

        content = _ENCODER.decode(window_ids)
        chunks.append(
            Chunk(
                chunk_index=chunk_index,
                content=content,
                content_tokens=len(window_ids),
                metadata={
                    **(base_metadata or {}),
                    "token_start": start,
                    "token_end": end,
                },
            )
        )
        chunk_index += 1
        if end == total:
            break
        start += step

    return chunks
