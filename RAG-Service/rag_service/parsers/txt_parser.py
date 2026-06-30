"""Plain text + Markdown parser.

For .txt and .md we decode bytes as UTF-8 (with BOM stripping and a
permissive fallback) and treat the whole document as a single page.
Markdown is left as-is — the chunker / embedder treats it as text, and
keeping the original markers actually helps retrieval (headings act as
strong anchors in the embedding space).
"""

from __future__ import annotations

from rag_service.parsers.types import ParsedDocument, ParsedPage


def parse_text(content: bytes) -> ParsedDocument:
    """Decode bytes to UTF-8 text; tolerate broken encodings."""
    try:
        text = content.decode("utf-8-sig")  # strips BOM if present
    except UnicodeDecodeError:
        # Some users upload Windows-1254 (Turkish) etc. Fall back without
        # raising; replacement chars are preferable to a failed upload.
        text = content.decode("utf-8", errors="replace")

    text = text.strip()
    return ParsedDocument(
        full_text=text,
        pages=[ParsedPage(page_number=1, text=text)],
        parser="text",
        extra={"byte_size": len(content)},
    )
