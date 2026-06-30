"""auth.py - Gateway JWT verification.

The Gateway (.NET, port 5000) issues HS256 JWTs for end users. Those
tokens are forwarded as `Authorization: Bearer <jwt>` either directly
by the frontend (dev) or by YARP when proxying through the gateway
(prod). This module decodes that token to extract the user id.

We deliberately keep auth conditional:
  - `require_user`: hard 401 if no/invalid token (document endpoints)
  - `optional_user`: returns None instead of raising (chat endpoint
    falls back to anonymous mode without RAG)

Token shape (issued by Gateway/src/Gateway.API/Services/AuthService.cs):
  alg=HS256, iss=Gateway.API, aud=Gateway.Clients
  claims: nameid (userId, GUID), email, exp, iat, ...
"""

from __future__ import annotations

from typing import Annotated

import jwt as pyjwt
from config import settings
from fastapi import Header, HTTPException, status
from pydantic import BaseModel

_BEARER_PREFIX = "bearer "

# .NET's ClaimTypes.NameIdentifier serializes to this URI-style claim
# name in the JWT. Some flows also include the short "nameid" or "sub"
# alias, so we check them in order.
_USER_ID_CLAIMS: tuple[str, ...] = (
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier",
    "nameid",
    "sub",
)


class GatewayUser(BaseModel):
    """The end-user identity extracted from the Gateway-issued JWT."""

    user_id: str
    email: str | None = None


def _extract_token(authorization: str | None) -> str | None:
    """Returns the token portion of a 'Bearer <token>' header, or None."""
    if not authorization:
        return None
    if not authorization.lower().startswith(_BEARER_PREFIX):
        return None
    return authorization[len(_BEARER_PREFIX) :].strip() or None


def _decode_gateway_token(token: str) -> GatewayUser:
    """Verify signature, issuer, audience, expiry. Raises 401 on any failure."""
    if not settings.gateway_jwt_secret:
        # Misconfiguration: secret not set but someone hit an auth-required
        # endpoint. Treat as server error so the operator notices.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth is not configured on this server",
        )

    try:
        payload = pyjwt.decode(
            token,
            settings.gateway_jwt_secret,
            algorithms=["HS256"],
            issuer=settings.gateway_jwt_issuer or None,
            audience=settings.gateway_jwt_audience or None,
            options={"require": ["exp"]},
        )
    except pyjwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        ) from exc
    except pyjwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        ) from exc

    user_id: str | None = None
    for claim in _USER_ID_CLAIMS:
        value = payload.get(claim)
        if value:
            user_id = str(value)
            break

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has no user id claim",
        )

    email = payload.get("email")
    return GatewayUser(user_id=user_id, email=str(email) if email else None)


def require_user(
    authorization: Annotated[str | None, Header()] = None,
) -> GatewayUser:
    """FastAPI dependency: 401 if no valid Bearer JWT."""
    token = _extract_token(authorization)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
        )
    return _decode_gateway_token(token)


def optional_user(
    authorization: Annotated[str | None, Header()] = None,
) -> GatewayUser | None:
    """FastAPI dependency: returns the user when a valid token is present,
    None otherwise. Never raises 401."""
    token = _extract_token(authorization)
    if token is None:
        return None
    try:
        return _decode_gateway_token(token)
    except HTTPException:
        # Bad token treated like no token for /api/chat so anonymous
        # local-dev clients (no Gateway) keep working.
        return None
