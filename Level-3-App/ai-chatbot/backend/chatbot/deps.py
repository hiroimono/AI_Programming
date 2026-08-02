"""FastAPI auth dependencies.

`get_current_admin` is the single seam where an incoming admin request is
authenticated AND the Row-Level Security tenant context is pinned for the
rest of the request. Every tenant-scoped handler depends on it (directly or
transitively), so no handler can query another tenant's data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import jwt as pyjwt
from chatbot.db import get_session, set_current_tenant
from chatbot.models import AdminUser
from chatbot.security import decode_token
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_BEARER_PREFIX = "bearer "
_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or missing credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


@dataclass(frozen=True)
class CurrentAdmin:
    """The verified admin behind the current request."""

    admin_id: UUID
    tenant_id: UUID
    role: str
    email: str


def _extract_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith(_BEARER_PREFIX):
        raise _UNAUTHENTICATED
    return authorization[len(_BEARER_PREFIX) :].strip()


async def get_current_admin(
    authorization: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_session),
) -> CurrentAdmin:
    """Decode the admin JWT, pin the RLS tenant GUC, load the live admin row."""
    token = _extract_bearer(authorization)
    try:
        claims = decode_token(token, expected_scope="admin")
    except (pyjwt.InvalidTokenError, ValueError) as exc:
        raise _UNAUTHENTICATED from exc

    try:
        admin_id = UUID(str(claims["sub"]))
        tenant_id = UUID(str(claims["tenant_id"]))
    except (KeyError, ValueError, TypeError) as exc:
        raise _UNAUTHENTICATED from exc

    # Pin RLS BEFORE any tenant-scoped query in downstream handlers.
    await set_current_tenant(session, tenant_id)

    # admin_users is RLS-exempt; still filter by id + tenant + active so a
    # deleted/disabled admin's un-expired token stops working immediately.
    admin = (
        await session.execute(
            select(AdminUser).where(
                AdminUser.id == admin_id,
                AdminUser.tenant_id == tenant_id,
                AdminUser.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if admin is None:
        raise _UNAUTHENTICATED

    return CurrentAdmin(
        admin_id=admin.id,
        tenant_id=admin.tenant_id,
        role=admin.role,
        email=admin.email,
    )
