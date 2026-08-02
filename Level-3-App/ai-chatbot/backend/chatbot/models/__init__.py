"""Model package.

Importing every model module here registers all tables against the single
Base.metadata, so `from chatbot.models import Base` in alembic/env.py sees
the complete schema for autogenerate.

RLS_TABLES lists the tenant-scoped data tables that get Row-Level Security
policies in the initial migration. tenants + admin_users are intentionally
excluded (login/administration are cross-tenant control-plane operations).
"""

from __future__ import annotations

from chatbot.models.base import Base
from chatbot.models.bot import Bot, BotConfig
from chatbot.models.conversation import Conversation, Message
from chatbot.models.document import Chunk, Document
from chatbot.models.tenant import AdminUser, Tenant
from chatbot.models.usage import UsageEvent

# Tables that enforce tenant isolation via RLS (see initial migration).
RLS_TABLES = (
    "bots",
    "bot_configs",
    "documents",
    "chunks",
    "conversations",
    "messages",
    "usage_events",
)

__all__ = [
    "Base",
    "Tenant",
    "AdminUser",
    "Bot",
    "BotConfig",
    "Document",
    "Chunk",
    "Conversation",
    "Message",
    "UsageEvent",
    "RLS_TABLES",
]
