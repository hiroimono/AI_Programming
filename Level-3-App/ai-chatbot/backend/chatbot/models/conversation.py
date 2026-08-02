"""Conversation + Message: chat sessions between an anonymous end-user (via
the widget) and a bot, plus the individual turns.

A conversation is tied to a bot and, for widget traffic, to an anonymous
session_id. Admin "live preview" conversations set is_preview=true so they
never count toward quota or analytics. Both tables carry tenant_id and are
under RLS.
"""

# pylint: disable=not-callable

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from chatbot.models.base import Base
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Conversation(Base):
    """One chat thread with a bot."""

    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_bot_created", "bot_id", "created_at"),)

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
        index=True,
    )
    # Anonymous widget session that owns this conversation (null for
    # admin-initiated preview threads).
    session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Admin live-preview threads: excluded from quota + analytics.
    is_preview: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # active | closed.
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Message(Base):
    """A single turn in a conversation."""

    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )

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
    conversation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # user | assistant | system.
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Retrieved source citations attached to an assistant message, e.g.
    # [{"document_id": "...", "file_name": "...", "score": 0.87}].
    sources: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(
        JSONB, nullable=True
    )
    # streaming | completed | aborted (incremental persist during SSE).
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
