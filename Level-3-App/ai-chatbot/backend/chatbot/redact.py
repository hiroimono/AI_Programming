"""Lightweight PII redaction (M8).

Regex-based scrubbing of common personal identifiers (email, phone, credit
card, IBAN). This is intentionally NOT applied before the LLM or retrieval:
the model needs the real message to answer well. It is applied only to the
copy we *persist* (message audit trail in the DB) and to anything we *log*,
so stored data and logs never accumulate raw PII.

A heavier NER solution (e.g. Presidio) was rejected for M8 as overkill for a
single-instance deployment; these patterns cover the high-frequency cases and
the seam (`redact`) stays swappable if we upgrade later.
"""

import re
from typing import Final, Pattern

# Order matters: IBAN and card run before phone, because the phone pattern can
# otherwise consume digit runs that belong to an account/card number.
_EMAIL: Final[Pattern[str]] = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)
# IBAN: 2 country letters + 2 check digits + up to 30 alphanumerics.
_IBAN: Final[Pattern[str]] = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
# Credit card: 13-19 digits, optionally split by spaces or hyphens.
_CARD: Final[Pattern[str]] = re.compile(r"\b(?:\d[ -]?){13,19}\b")
# Phone: optional +country code, then 7-14 digits with common separators.
_PHONE: Final[Pattern[str]] = re.compile(r"(?<!\w)\+?\d[\d\s().-]{6,}\d(?!\w)")

# (pattern, placeholder) applied in this exact sequence.
_RULES: Final[tuple[tuple[Pattern[str], str], ...]] = (
    (_EMAIL, "[EMAIL_REDACTED]"),
    (_IBAN, "[IBAN_REDACTED]"),
    (_CARD, "[CARD_REDACTED]"),
    (_PHONE, "[PHONE_REDACTED]"),
)


def redact(text: str) -> str:
    """Return `text` with recognized PII replaced by typed placeholders.

    Idempotent for already-redacted text (placeholders contain no PII).
    """
    if not text:
        return text
    for pattern, placeholder in _RULES:
        text = pattern.sub(placeholder, text)
    return text
