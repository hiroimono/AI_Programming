"""Password hashing (argon2) and JWT minting/verification.

One module for all cryptographic token concerns so the rest of the app never
touches PyJWT or argon2 directly.

Tokens are HS256, signed with the single JWT_SECRET. A `scope` claim tells the
three token kinds apart on one secret:
    - scope="admin"   → tenant admin panel session (this milestone, M1)
    - scope="widget"  → anonymous end-user widget session (M4)
    - scope="preview" → short-lived admin live-preview session (M4)
Splitting to separate secrets later is a drop-in change (add key per scope).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt as pyjwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from chatbot.config import get_settings

# argon2id with library defaults (safe, memory-hard). Reused across calls;
# PasswordHasher is stateless and thread-safe.
_HASHER = PasswordHasher()


def hash_password(plain: str) -> str:
    """Return an argon2id hash string (includes salt + params)."""
    return _HASHER.hash(plain)


def verify_password(password_hash: str, plain: str) -> bool:
    """Constant-time-ish verify; False on mismatch instead of raising."""
    try:
        return _HASHER.verify(password_hash, plain)
    except VerifyMismatchError:
        return False


def _secret() -> str:
    settings = get_settings()
    # pydantic v2 SecretStr default confuses pylint/pyright on this method.
    secret = settings.jwt_secret.get_secret_value()  # type: ignore[attr-defined]  # pylint: disable=no-member
    if not secret:
        raise RuntimeError("JWT_SECRET is not configured in .env")
    return secret


def create_token(
    *,
    subject: str,
    scope: str,
    ttl_seconds: int,
    extra_claims: dict[str, Any] | None = None,
) -> tuple[str, int]:
    """Mint an HS256 token.

    Returns (token, expires_in_seconds). `subject` becomes the `sub` claim.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "scope": scope,
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
    }
    if extra_claims:
        payload.update(extra_claims)
    token = pyjwt.encode(payload, _secret(), algorithm=settings.jwt_algorithm)
    return token, ttl_seconds


def create_admin_token(admin_id: UUID, tenant_id: UUID, role: str) -> tuple[str, int]:
    """Mint a tenant-admin session token (scope=admin)."""
    return create_token(
        subject=str(admin_id),
        scope="admin",
        ttl_seconds=get_settings().admin_token_ttl,
        extra_claims={"tenant_id": str(tenant_id), "role": role},
    )


def decode_token(token: str, *, expected_scope: str | None = None) -> dict[str, Any]:
    """Verify signature + expiry and return the claims.

    Raises PyJWT exceptions on invalid/expired tokens; ValueError on a
    scope mismatch (structurally valid but wrong token kind).
    """
    settings = get_settings()
    payload = pyjwt.decode(
        token,
        _secret(),
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "sub", "scope"]},
    )
    if expected_scope is not None and payload.get("scope") != expected_scope:
        raise ValueError(
            f"Token scope '{payload.get('scope')}' != expected '{expected_scope}'"
        )
    return payload
