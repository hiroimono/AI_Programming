"""Widget chat endpoint (M5) — Server-Sent Events (SSE).

POST /api/widget/chat streams the assistant reply back token-by-token over
`text/event-stream`. SSE (a one-way HTTP streaming standard the browser reads
via EventSource) is simpler than WebSockets here: the widget only needs the
server→client direction, and it auto-reconnects.

The heavy lifting lives in chat.run_chat_turn (an async generator of event
dicts); this router only validates the request, does a fast conversation
ownership pre-check (so a bad conversation_id is a clean 404 before the stream
starts), and formats each event dict onto the SSE wire.
"""

import json
from typing import AsyncIterator

from chatbot import chat
from chatbot.db import get_session
from chatbot.deps import CurrentWidget, get_current_widget
from chatbot.models import Conversation
from chatbot.ratelimit import limiter, widget_chat_limit
from chatbot.schemas import ChatRequest
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/widget", tags=["chat"])

_CONVERSATION_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
)

# SSE anti-buffering headers: keep the connection open and stop proxies from
# holding the response back.
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _sse_format(event: str, data: object) -> str:
    """Render one SSE frame: `event:` line + JSON `data:` line + blank line."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _event_stream(
    current: CurrentWidget, body: ChatRequest
) -> AsyncIterator[str]:
    async for event in chat.run_chat_turn(
        tenant_id=current.tenant_id,
        bot_id=current.bot_id,
        session_id=current.session_id,
        is_preview=current.is_preview,
        user_message=body.message,
        conversation_id=body.conversation_id,
    ):
        yield _sse_format(event["event"], event["data"])


@router.post("/chat")
@limiter.limit(widget_chat_limit)
async def chat_stream(
    request: Request,  # pylint: disable=unused-argument
    body: ChatRequest,
    current: CurrentWidget = Depends(get_current_widget),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Stream an assistant reply for one user turn as SSE."""
    # Ownership pre-check so an invalid conversation_id is a clean 404 (once
    # the SSE stream starts we can only report errors as in-band events). RLS
    # was already pinned by get_current_widget on this session.
    if body.conversation_id is not None:
        owned = (
            await session.execute(
                select(Conversation.id).where(
                    Conversation.id == body.conversation_id,
                    Conversation.session_id == current.session_id,
                )
            )
        ).scalar_one_or_none()
        if owned is None:
            raise _CONVERSATION_NOT_FOUND

    return StreamingResponse(
        _event_stream(current, body),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
