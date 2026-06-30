"""Internal JWT verification for service-to-service calls.

rag-service is NOT exposed directly to browsers. The only clients are
consuming app backends (Level-2 writer backend, Level-3 chatbot
backend). They mint a short-lived HS256 JWT for each request with the
acting user's identity and pass it as `Authorization: Bearer <jwt>`.

Why JWT (and not e.g. a shared API key)?
  - User scoping: tokens carry (app_id, user_id, conversation_id) so
    endpoints can never accept a forged user_id from the request body.
  - Expiry: a leaked token has a 5-minute blast radius.
  - Asymmetric upgrade path: today HS256 with a shared secret; later
    RS256 with per-backend public keys is a drop-in.

Token claims contract:
  {
    "iss": "<backend-name>",         # informational
    "sub": "<user-id>",              # mapped to InternalIdentity.user_id
    "app_id": "level-2-writer",      # selects rag schema
    "conversation_id": "<uuid|null>",# optional retrieval scope
    "iat": <unix>,
    "exp": <unix>
  }
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import jwt as pyjwt
from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel
from rag_service.config import get_settings

# Standard "Bearer " prefix; case-insensitive per RFC 6750.
_BEARER_PREFIX = "bearer "


class InternalIdentity(BaseModel):
    """The verified identity extracted from a valid JWT.

    Endpoint handlers receive this via FastAPI's Depends() and use it
    to scope every DB query. Request bodies must NEVER carry app_id or
    user_id — only this trusted object does.
    """

    app_id: str
    user_id: str
    conversation_id: UUID | None = None


def _extract_token(authorization: str | None) -> str:
    """Pull the bare token out of the Authorization header."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not authorization.lower().startswith(_BEARER_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must start with 'Bearer '",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return authorization[len(_BEARER_PREFIX) :].strip()


def verify_internal_jwt(
    authorization: Annotated[str | None, Header()] = None,
) -> InternalIdentity:
    """FastAPI dependency: parse + verify token, return InternalIdentity.

    Raises 401 on missing/invalid/expired token; 403 on a structurally
    valid token whose claims are incomplete (we treat that as a misuse
    by the calling backend, not by the end user).
    """
    settings = get_settings()
    # pydantic v2 Field default trips type inference on .get_secret_value()
    secret = settings.internal_jwt_secret.get_secret_value()  # type: ignore[attr-defined]  # pylint: disable=no-member
    if not secret:
        # Server-side misconfig: refuse all requests rather than accept
        # tokens signed with an empty secret.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="rag-service: INTERNAL_JWT_SECRET is not configured",
        )

    token = _extract_token(authorization)

    try:
        payload = pyjwt.decode(
            token,
            secret,
            algorithms=[settings.internal_jwt_algorithm],
            # iss is informational; we don't restrict it yet.
            options={"require": ["exp", "sub"]},
        )
    except pyjwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except pyjwt.InvalidTokenError as exc:
        # Covers bad signature, malformed token, missing required claims.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    app_id = payload.get("app_id")
    user_id = payload.get("sub")
    if not app_id or not user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token missing required claims (app_id, sub)",
        )

    conv_raw = payload.get("conversation_id")
    conversation_id: UUID | None = None
    if conv_raw:
        try:
            conversation_id = UUID(str(conv_raw))
        except (ValueError, TypeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token conversation_id is not a valid UUID",
            ) from exc

    return InternalIdentity(
        app_id=app_id,
        user_id=user_id,
        conversation_id=conversation_id,
    )


# Convenience type alias so endpoint signatures stay readable:
#     async def handler(identity: AuthedIdentity, ...): ...
AuthedIdentity = Annotated[InternalIdentity, Depends(verify_internal_jwt)]
