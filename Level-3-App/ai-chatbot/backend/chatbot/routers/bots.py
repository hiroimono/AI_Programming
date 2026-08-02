"""Bot + BotConfig CRUD (tenant-scoped).

Every route depends on `get_current_admin`, which pins the RLS tenant GUC for
the request. tenant_id is taken from the authenticated admin (never the body),
and RLS enforces the same boundary at the database layer, so one tenant can
never see or mutate another tenant's bots.

RLS + transaction note: the GUC is transaction-local (set_config is_local).
After a commit the GUC is cleared, so write routes re-pin the tenant before
re-loading the row for the response.
"""

from __future__ import annotations

from uuid import UUID

from chatbot.db import get_session, set_current_tenant
from chatbot.deps import CurrentAdmin, get_current_admin
from chatbot.models import Bot, BotConfig
from chatbot.schemas import BotConfigOut, BotConfigUpdate, BotCreate, BotOut, BotUpdate
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

router = APIRouter(prefix="/api/bots", tags=["bots"])

_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found"
)


async def _load_bot(session: AsyncSession, tenant_id: UUID, bot_id: UUID) -> Bot:
    """Fetch one bot (with its config eagerly loaded) or raise 404.

    The tenant_id filter is belt-and-suspenders on top of RLS; selectinload
    avoids an async lazy-load when the config is serialized.
    """
    bot = (
        await session.execute(
            select(Bot)
            .options(selectinload(Bot.config))
            .where(Bot.id == bot_id, Bot.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if bot is None:
        raise _NOT_FOUND
    return bot


@router.post("", response_model=BotOut, status_code=status.HTTP_201_CREATED)
async def create_bot(
    body: BotCreate,
    current: CurrentAdmin = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> BotOut:
    """Create a bot plus its default BotConfig (1-to-1)."""
    bot = Bot(
        tenant_id=current.tenant_id,
        name=body.name,
        allowed_domains=body.allowed_domains,
    )
    # Config defaults come from the model column defaults.
    bot.config = BotConfig(tenant_id=current.tenant_id)
    session.add(bot)
    await session.commit()

    # GUC was cleared by the commit; re-pin before reading back.
    await set_current_tenant(session, current.tenant_id)
    loaded = await _load_bot(session, current.tenant_id, bot.id)
    return BotOut.model_validate(loaded)


@router.get("", response_model=list[BotOut])
async def list_bots(
    current: CurrentAdmin = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[BotOut]:
    """List all bots owned by the current tenant."""
    bots = (
        (
            await session.execute(
                select(Bot)
                .options(selectinload(Bot.config))
                .where(Bot.tenant_id == current.tenant_id)
                .order_by(Bot.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [BotOut.model_validate(bot) for bot in bots]


@router.get("/{bot_id}", response_model=BotOut)
async def get_bot(
    bot_id: UUID,
    current: CurrentAdmin = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> BotOut:
    bot = await _load_bot(session, current.tenant_id, bot_id)
    return BotOut.model_validate(bot)


@router.patch("/{bot_id}", response_model=BotOut)
async def update_bot(
    bot_id: UUID,
    body: BotUpdate,
    current: CurrentAdmin = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> BotOut:
    bot = await _load_bot(session, current.tenant_id, bot_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(bot, field, value)
    await session.commit()

    await set_current_tenant(session, current.tenant_id)
    loaded = await _load_bot(session, current.tenant_id, bot_id)
    return BotOut.model_validate(loaded)


@router.delete(
    "/{bot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_bot(
    bot_id: UUID,
    current: CurrentAdmin = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    bot = await _load_bot(session, current.tenant_id, bot_id)
    await session.delete(bot)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{bot_id}/config", response_model=BotConfigOut)
async def get_bot_config(
    bot_id: UUID,
    current: CurrentAdmin = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> BotConfigOut:
    bot = await _load_bot(session, current.tenant_id, bot_id)
    if bot.config is None:
        raise _NOT_FOUND
    return BotConfigOut.model_validate(bot.config)


@router.patch("/{bot_id}/config", response_model=BotConfigOut)
async def update_bot_config(
    bot_id: UUID,
    body: BotConfigUpdate,
    current: CurrentAdmin = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> BotConfigOut:
    bot = await _load_bot(session, current.tenant_id, bot_id)
    if bot.config is None:
        raise _NOT_FOUND
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(bot.config, field, value)
    await session.commit()

    await set_current_tenant(session, current.tenant_id)
    loaded = await _load_bot(session, current.tenant_id, bot_id)
    return BotConfigOut.model_validate(loaded.config)
