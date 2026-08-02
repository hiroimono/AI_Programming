"""UsageEvent: one row per billable OpenAI call, for metering + billing.

Written on every chat completion, embedding batch, and document upload so
we can enforce quotas (later milestones) and export to Stripe metered
billing (Phase 6). Carries tenant_id and is under RLS.
"""

# pylint: disable=not-callable

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from chatbot.models.base import Base
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column


class UsageEvent(Base):
    """A single metered unit of OpenAI usage."""

    __tablename__ = "usage_events"
    __table_args__ = (
        # Aggregation queries scan by tenant over a time range.
        {"comment": "One row per billable OpenAI call."},
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
    # Nullable: some events (e.g. tenant-level) are not bot-specific.
    bot_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("bots.id", ondelete="SET NULL"),
        nullable=True,
    )
    # chat | embedding | document_upload.
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(
        Numeric(10, 6), nullable=False, server_default=text("0")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
