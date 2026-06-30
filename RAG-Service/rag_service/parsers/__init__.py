"""Parser dispatcher.

`parse(content, mime_type, filename)` picks the right parser based on
MIME type, with a filename-extension fallback. All parsers return the
same `ParsedDocument` shape so the chunker / embedder downstream are
parser-agnostic.

Supported (MVP):
  - PDF   (application/pdf)
  - DOCX  (application/vnd.openxmlformats-officedocument.wordprocessingml.document)
  - XLSX  (application/vnd.openxmlformats-officedocument.spreadsheetml.sheet)
  - TXT / MD / CSV (text/*)

OCR (images) is deliberately out of scope for the MVP; requires the
Tesseract native binary and pulls in pillow + pytesseract.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from rag_service.parsers.docx_parser import parse_docx
from rag_service.parsers.pdf_parser import parse_pdf
from rag_service.parsers.txt_parser import parse_text
from rag_service.parsers.types import ParsedDocument, ParsedPage
from rag_service.parsers.xlsx_parser import parse_xlsx

__all__ = ["parse", "UnsupportedFileTypeError", "ParsedDocument", "ParsedPage"]


class UnsupportedFileTypeError(ValueError):
    """Raised when no parser knows how to handle the given file."""


# Normalized MIME types we accept. Keep the table small and explicit so
# we never silently try to parse an executable as text.
_MIME_DISPATCH = {
    "application/pdf": parse_pdf,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": parse_docx,
    "application/msword": parse_docx,  # legacy .doc clients still send this header for .docx
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": parse_xlsx,
    "text/plain": parse_text,
    "text/markdown": parse_text,
    "text/csv": parse_text,
}

# Extension fallback used when the upload's mime is missing or generic
# (application/octet-stream is common from drag-and-drop on some browsers).
_EXT_DISPATCH = {
    ".pdf": parse_pdf,
    ".docx": parse_docx,
    ".xlsx": parse_xlsx,
    ".txt": parse_text,
    ".md": parse_text,
    ".csv": parse_text,
}


def parse(
    content: bytes, mime_type: str | None, filename: str | None
) -> ParsedDocument:
    """Route to the correct parser. Returns a normalized ParsedDocument."""
    if mime_type:
        parser_fn = _MIME_DISPATCH.get(mime_type.lower())
        if parser_fn is not None:
            return parser_fn(content)

    if filename:
        ext = PurePosixPath(filename).suffix.lower()
        parser_fn = _EXT_DISPATCH.get(ext)
        if parser_fn is not None:
            return parser_fn(content)

    raise UnsupportedFileTypeError(
        f"No parser for mime_type={mime_type!r} filename={filename!r}"
    )
