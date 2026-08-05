"""Unit tests for PII redaction (M8, Slice C)."""

from chatbot.redact import redact


def test_redacts_email():
    assert redact("mail me at john.doe@example.com please") == (
        "mail me at [EMAIL_REDACTED] please"
    )


def test_redacts_phone():
    out = redact("call +49 170 1234567 tomorrow")
    assert "[PHONE_REDACTED]" in out
    assert "1234567" not in out


def test_redacts_credit_card():
    out = redact("card 4111 1111 1111 1111 expires soon")
    assert "[CARD_REDACTED]" in out
    assert "4111" not in out


def test_redacts_iban():
    out = redact("account DE89370400440532013000 here")
    assert "[IBAN_REDACTED]" in out
    assert "DE89370400440532013000" not in out


def test_leaves_clean_text_unchanged():
    text = "What is your refund policy?"
    assert redact(text) == text


def test_is_idempotent():
    once = redact("reach me: a@b.com")
    assert redact(once) == once


def test_handles_empty_string():
    assert redact("") == ""
