"""Anonymous widget auth plane (M4).

Two endpoints the embeddable widget talks to before any chat happens:

- POST /api/widget/session  — PUBLIC. The embed sends its bot_id + tenant_id
  (both public, unguessable UUIDs) and its browser Origin. We pin RLS to the
  claimed tenant and load the bot; RLS makes the (tenant_id, bot_id) pair
  self-validating (a wrong tenant claim finds no bot → 404). We then check the
  bot is active and the Origin is whitelisted, and mint a 24h widget token.

- GET /api/widget/config    — widget/preview token. Re-fetches the public bot
  config on remount without opening a new session (preserves session_id).

No conversation row is created here; that happens on the first chat turn (M5).
"""

import secrets
from uuid import UUID

from chatbot.db import get_session, set_current_tenant
from chatbot.deps import CurrentWidget, get_current_widget
from chatbot.models import Bot
from chatbot.schemas import WidgetConfigOut, WidgetSessionRequest, WidgetSessionResponse
from chatbot.ratelimit import limiter, widget_session_limit
from chatbot.security import create_widget_token
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

router = APIRouter(prefix="/api/widget", tags=["widget"])

# Opaque anonymous session id. token_urlsafe(24) → 32 chars, fits String(64).
_SESSION_ID_BYTES = 24

_BOT_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found"
)
_BOT_DISABLED = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN, detail="Bot is not active"
)
_ORIGIN_NOT_ALLOWED = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN, detail="Origin not allowed for this bot"
)


def _origin_allowed(origin: str | None, allowed_domains: list[str]) -> bool:
    """Origin whitelist check (defense-in-depth on top of the UUID pair).

    Empty allowed_domains → allow any origin (MVP: widget works out of the
    box; a tenant opts into enforcement by listing domains). Matching is a
    case-insensitive exact compare after stripping a trailing slash.
    """
    if not allowed_domains:
        return True
    if not origin:
        return False
    norm = origin.rstrip("/").lower()
    return any(norm == d.rstrip("/").lower() for d in allowed_domains)


async def _load_bot(session: AsyncSession, tenant_id: UUID, bot_id: UUID) -> Bot:
    """Load a bot (+config) under the already-pinned RLS tenant, or 404."""
    bot = (
        await session.execute(
            select(Bot)
            .options(selectinload(Bot.config))
            .where(Bot.id == bot_id, Bot.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if bot is None:
        raise _BOT_NOT_FOUND
    return bot


def _config_out(bot: Bot) -> WidgetConfigOut:
    """Project a bot + its config into the browser-safe widget config DTO."""
    config = bot.config
    return WidgetConfigOut(
        bot_id=bot.id,
        name=bot.name,
        welcome_message=(
            config.welcome_message if config else "Hi! How can I help you today?"
        ),
        suggested_questions=(config.suggested_questions if config else []),
        primary_color=(config.primary_color if config else "#2563eb"),
    )


@router.post(
    "/session",
    response_model=WidgetSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(widget_session_limit)
async def open_widget_session(
    request: Request,  # pylint: disable=unused-argument
    body: WidgetSessionRequest,
    origin: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> WidgetSessionResponse:
    """Open an anonymous widget session and mint a 24h widget token."""
    # Pin RLS to the CLAIMED tenant; the bot lookup then self-validates the
    # (tenant_id, bot_id) pair — a forged tenant simply sees no bot.
    await set_current_tenant(session, body.tenant_id)
    bot = await _load_bot(session, body.tenant_id, body.bot_id)

    if bot.status != "active":
        raise _BOT_DISABLED
    if not _origin_allowed(origin, bot.allowed_domains):
        raise _ORIGIN_NOT_ALLOWED

    session_id = secrets.token_urlsafe(_SESSION_ID_BYTES)
    token, expires_in = create_widget_token(
        tenant_id=body.tenant_id, bot_id=body.bot_id, session_id=session_id
    )
    return WidgetSessionResponse(
        access_token=token,
        expires_in=expires_in,
        session_id=session_id,
        config=_config_out(bot),
    )


@router.get("/config", response_model=WidgetConfigOut)
async def get_widget_config(
    current: CurrentWidget = Depends(get_current_widget),
    session: AsyncSession = Depends(get_session),
) -> WidgetConfigOut:
    """Re-fetch the public bot config for an existing widget/preview session."""
    bot = await _load_bot(session, current.tenant_id, current.bot_id)
    if bot.status != "active":
        raise _BOT_DISABLED
    return _config_out(bot)
