"""Tenant + AdminUser: our customers (companies) and the people who manage
their bots.

These two tables are NOT under RLS: login must look up an AdminUser by email
BEFORE any tenant context exists, and tenant/user administration is a
cross-tenant control-plane concern. All tenant-scoped DATA tables (bots,
documents, conversations, ...) ARE under RLS. Application code still filters
these two tables by tenant_id explicitly where relevant.
"""

# pylint: disable=not-callable
# SQLAlchemy's `func` namespace generates attributes dynamically.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from chatbot.models.base import Base
from sqlalchemy import Boolean, DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Tenant(Base):
    """A customer company. Top of the ownership hierarchy."""

    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Billing tier: free | pro | enterprise. Enforced in later milestones.
    plan: Mapped[str] = mapped_column(String(20), nullable=False, default="free")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    admins: Mapped[list["AdminUser"]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AdminUser(Base):
    """A person who signs into the admin panel to manage a tenant's bots."""

    __tablename__ = "admin_users"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Globally unique so login can find the user without a tenant context.
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    # argon2 password hash (never the plaintext).
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # owner | editor | viewer.
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="owner")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="admins")
