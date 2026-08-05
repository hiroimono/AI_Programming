"""M8 rate-limit tests.

The limiter is disabled globally in conftest so the rest of the suite can fire
rapid auth calls. Here we enable it, shrink the login cap to a tiny value, and
assert that exceeding it returns 429. All requests share the same client IP key
under httpx's ASGI transport, so the cap applies across the loop.
"""

from __future__ import annotations

from typing import Callable

import pytest
from chatbot.config import get_settings
from chatbot.ratelimit import limiter
from httpx import AsyncClient


@pytest.fixture
def _enable_limiter() -> Callable[[], None]:
    """Enable the limiter for one test and reset its counters afterwards."""
    limiter.enabled = True
    limiter.reset()
    yield
    limiter.reset()
    limiter.enabled = False


@pytest.mark.asyncio
async def test_login_is_rate_limited(
    client: AsyncClient,
    make_email: Callable[[], str],
    monkeypatch: pytest.MonkeyPatch,
    _enable_limiter: None,
) -> None:
    # Shrink the login cap so we hit it in a handful of calls.
    monkeypatch.setattr(get_settings(), "rate_limit_login", "3/minute")

    # A never-registered email keeps every attempt a clean 401 (or 429 once
    # the cap trips) without side effects.
    email = make_email()
    codes = [
        (
            await client.post(
                "/api/auth/login", json={"email": email, "password": "wrong-pw"}
            )
        ).status_code
        for _ in range(5)
    ]

    assert codes[:3] == [401, 401, 401]
    assert 429 in codes[3:]
