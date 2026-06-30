"""PDF text extraction via pypdf.

We use pypdf (pure-Python, no native deps) for the MVP. It handles most
text-based PDFs well. Scanned/image PDFs return empty text and would
need OCR — currently out of scope (see strategy doc).
"""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader

from rag_service.parsers.types import ParsedDocument, ParsedPage

# Inserted between concatenated page texts in `full_text`. The chunker
# can split on this sentinel to keep page boundaries clean.
PAGE_SEPARATOR = "\n\n\f\n\n"  # form-feed is rare inside extracted text


def parse_pdf(content: bytes) -> ParsedDocument:
    """Extract text from PDF bytes, page by page."""
    reader = PdfReader(BytesIO(content))
    pages: list[ParsedPage] = []
    for idx, page in enumerate(reader.pages, start=1):
        # extract_text() returns None for image-only pages; normalize.
        raw = page.extract_text() or ""
        text = raw.strip()
        pages.append(ParsedPage(page_number=idx, text=text))

    full_text = PAGE_SEPARATOR.join(p.text for p in pages if p.text)
    return ParsedDocument(
        full_text=full_text,
        pages=pages,
        parser="pypdf",
        extra={"page_count": len(pages)},
    )
