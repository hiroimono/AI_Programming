"""Auth plane 1: tenant/admin registration, login, and identity.

Endpoints:
    POST /api/auth/register  public self-service signup (tenant + owner admin)
    POST /api/auth/login     email + password -> admin JWT
    GET  /api/auth/me        current admin + tenant (requires Bearer)

Registration is deliberately a standalone public route so it can later be
gated (invite-only / admin-created tenants) without touching login.
"""

from __future__ import annotations

from chatbot.db import get_session
from chatbot.deps import CurrentAdmin, get_current_admin
from chatbot.models import AdminUser, Tenant
from chatbot.schemas import (
    AdminOut,
    LoginRequest,
    MeResponse,
    RegisterRequest,
    TenantOut,
    TokenResponse,
)
from chatbot.security import create_admin_token, hash_password, verify_password
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Create a tenant and its first owner admin, then auto-login."""
    email = body.email.lower()

    tenant = Tenant(name=body.tenant_name)
    admin = AdminUser(
        tenant=tenant,
        email=email,
        password_hash=hash_password(body.password),
        role="owner",
    )
    session.add(tenant)
    session.add(admin)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        # Global unique constraint on admin_users.email.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from exc

    await session.refresh(admin)
    token, expires_in = create_admin_token(admin.id, tenant.id, admin.role)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Verify credentials and mint an admin session token."""
    email = body.email.lower()
    admin = (
        await session.execute(select(AdminUser).where(AdminUser.email == email))
    ).scalar_one_or_none()

    # Same 401 whether the email is unknown or the password is wrong, so we
    # don't leak which emails are registered.
    if (
        admin is None
        or not admin.is_active
        or not verify_password(admin.password_hash, body.password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token, expires_in = create_admin_token(admin.id, admin.tenant_id, admin.role)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=MeResponse)
async def me(
    current: CurrentAdmin = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> MeResponse:
    """Return the authenticated admin and their tenant."""
    tenant = (
        await session.execute(select(Tenant).where(Tenant.id == current.tenant_id))
    ).scalar_one()
    return MeResponse(
        admin=AdminOut(
            id=current.admin_id,
            email=current.email,
            role=current.role,
            tenant_id=current.tenant_id,
        ),
        tenant=TenantOut.model_validate(tenant),
    )
