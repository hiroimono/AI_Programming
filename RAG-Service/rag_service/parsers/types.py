"""Shared types returned by all parsers.

Parsers normalize wildly different input formats (PDF pages, DOCX
paragraphs, XLSX cells, plain text) into a single shape the chunker
understands. Page-level metadata is preserved when possible so that
retrieved chunks can cite "PDF page 4" or "Sheet Q3, row 12".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedPage:
    """One page / sheet / section of the source document.

    `page_number` is 1-based for human display ("page 1 of 12").
    `text` is plain UTF-8 with no markup.
    """

    page_number: int
    text: str
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    """Output of every parser. `full_text` is the join of all pages with
    a page-break separator the chunker can recognize if it wants to
    avoid splitting across pages."""

    full_text: str
    pages: list[ParsedPage]
    parser: str  # parser name, e.g. "pypdf", "python-docx", "openpyxl"
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def page_count(self) -> int:
        return len(self.pages)
