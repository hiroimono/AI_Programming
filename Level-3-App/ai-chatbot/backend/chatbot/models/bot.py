"""Bot + BotConfig: an assistant a tenant configures and embeds.

A tenant can own multiple bots (e.g. Sales bot, Support bot). Each bot has
exactly one BotConfig (1-to-1) holding its editable settings, and a list of
allowed domains it may be embedded on (Origin whitelist for widget sessions).

Both tables carry tenant_id and are under RLS.
"""

# pylint: disable=not-callable

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from chatbot.models.base import Base
from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Bot(Base):
    """An assistant instance owned by a tenant."""

    __tablename__ = "bots"

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
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # active | disabled.
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    # List of origins this bot may be embedded on, e.g.
    # ["https://acme.com", "https://shop.acme.com"]. Validated per widget session.
    allowed_domains: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    config: Mapped[Optional["BotConfig"]] = relationship(
        back_populates="bot",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )


class BotConfig(Base):
    """Editable settings for one bot (1-to-1 with Bot)."""

    __tablename__ = "bot_configs"

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
    bot_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("bots.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    welcome_message: Mapped[str] = mapped_column(
        Text, nullable=False, default="Hi! How can I help you today?"
    )
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(
        String(50), nullable=False, default="gpt-4o-mini"
    )
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.2)
    suggested_questions: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    primary_color: Mapped[str] = mapped_column(
        String(20), nullable=False, default="#2563eb"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    bot: Mapped["Bot"] = relationship(back_populates="config")
