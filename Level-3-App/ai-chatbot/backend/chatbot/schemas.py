"""Pydantic request/response DTOs for the admin API (auth + bots).

Kept separate from ORM models: the API contract (what browsers send/receive)
must never leak internal columns like password_hash.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
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


# ─── Bots + BotConfig (M2) ──────────────────────────────────────────
# tenant_id is NEVER accepted from the client: it is taken from the
# authenticated admin and enforced again by RLS. Clients only ever send
# the bot's own fields.

BotStatus = Literal["active", "disabled"]


class BotCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    allowed_domains: list[str] = Field(default_factory=list)


class BotUpdate(BaseModel):
    """PATCH: only provided fields are changed (exclude_unset)."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    status: Optional[BotStatus] = None
    allowed_domains: Optional[list[str]] = None


class BotConfigUpdate(BaseModel):
    welcome_message: Optional[str] = Field(default=None, max_length=2000)
    system_prompt: Optional[str] = Field(default=None, max_length=8000)
    model: Optional[str] = Field(default=None, min_length=1, max_length=50)
    temperature: Optional[float] = Field(default=None, ge=0, le=2)
    suggested_questions: Optional[list[str]] = None
    primary_color: Optional[str] = Field(default=None, min_length=1, max_length=20)


class BotConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    welcome_message: str
    system_prompt: Optional[str]
    model: str
    temperature: float
    suggested_questions: list[str]
    primary_color: str


class BotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: str
    allowed_domains: list[str]
    created_at: datetime
    config: Optional[BotConfigOut] = None


# ─── Documents (M3 — RAG training) ──────────────────────────────────
# Read-only DTO: uploads come in as multipart/form-data (an UploadFile),
# not JSON, so there is no DocumentCreate schema — the router reads the
# file bytes directly. status is one of: uploaded | ready | failed.

DocumentStatus = Literal["uploaded", "processing", "ready", "failed"]


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_name: str
    file_type: str
    mime_type: str
    file_size_bytes: int
    status: str
    error_message: Optional[str]
    chunk_count: int
    created_at: datetime
