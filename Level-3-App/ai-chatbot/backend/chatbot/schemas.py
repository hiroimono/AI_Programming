"""Pydantic request/response DTOs for the auth plane.

Kept separate from ORM models: the API contract (what browsers send/receive)
must never leak internal columns like password_hash.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """Self-service signup: creates a tenant + its first owner admin."""

    tenant_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """OAuth2-style token envelope returned by register + login."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    role: str
    tenant_id: UUID


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    plan: str


class MeResponse(BaseModel):
    admin: AdminOut
    tenant: TenantOut
