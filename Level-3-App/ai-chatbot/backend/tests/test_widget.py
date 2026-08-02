"""M4 widget auth-plane tests (run against the real Neon dev DB).

Covers the anonymous session mint (Option D: the embed carries bot_id +
tenant_id and RLS self-validates the pair), the Origin whitelist, the
widget/preview scope split, and the admin preview-session endpoint.
"""

from __future__ import annotations

import uuid
from typing import Callable

import pytest
from chatbot.security import decode_token
from httpx import AsyncClient
from tests.conftest import register_admin

_ACME_ORIGIN = "https://acme.com"
_EVIL_ORIGIN = "https://evil.example"


async def _tenant_id(client: AsyncClient, auth: dict[str, str]) -> str:
    """Read the authenticated admin's tenant_id from /api/auth/me."""
    resp = await client.get("/api/auth/me", headers=auth)
    assert resp.status_code == 200, resp.text
    return resp.json()["admin"]["tenant_id"]


async def _create_bot(
    client: AsyncClient,
    auth: dict[str, str],
    *,
    allowed_domains: list[str] | None = None,
) -> str:
    """Create a bot and return its id."""
    resp = await client.post(
        "/api/bots",
        headers=auth,
        json={"name": "Support", "allowed_domains": allowed_domains or []},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_open_session_success(
    client: AsyncClient, make_email: Callable[[], str]
) -> None:
    auth = await register_admin(client, make_email())
    tenant_id = await _tenant_id(client, auth)
    bot_id = await _create_bot(client, auth)

    resp = await client.post(
        "/api/widget/session",
        json={"bot_id": bot_id, "tenant_id": tenant_id},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 86400
    assert data["session_id"]
    assert data["config"]["bot_id"] == bot_id
    assert data["config"]["welcome_message"]

    claims = decode_token(data["access_token"], expected_scope="widget")
    assert claims["tenant_id"] == tenant_id
    assert claims["bot_id"] == bot_id
    assert claims["sub"] == data["session_id"]


@pytest.mark.asyncio
async def test_open_session_unknown_bot_404(
    client: AsyncClient, make_email: Callable[[], str]
) -> None:
    auth = await register_admin(client, make_email())
    tenant_id = await _tenant_id(client, auth)

    resp = await client.post(
        "/api/widget/session",
        json={"bot_id": str(uuid.uuid4()), "tenant_id": tenant_id},
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_open_session_wrong_tenant_404(
    client: AsyncClient, make_email: Callable[[], str]
) -> None:
    """Option-D security core: a real bot_id + someone else's tenant_id must
    find no row (RLS), never leak or authorize."""
    auth_a = await register_admin(client, make_email())
    bot_id = await _create_bot(client, auth_a)

    auth_b = await register_admin(client, make_email())
    tenant_b = await _tenant_id(client, auth_b)

    resp = await client.post(
        "/api/widget/session",
        json={"bot_id": bot_id, "tenant_id": tenant_b},
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_open_session_disabled_bot_403(
    client: AsyncClient, make_email: Callable[[], str]
) -> None:
    auth = await register_admin(client, make_email())
    tenant_id = await _tenant_id(client, auth)
    bot_id = await _create_bot(client, auth)

    patch = await client.patch(
        f"/api/bots/{bot_id}", headers=auth, json={"status": "disabled"}
    )
    assert patch.status_code == 200, patch.text

    resp = await client.post(
        "/api/widget/session",
        json={"bot_id": bot_id, "tenant_id": tenant_id},
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_origin_whitelist(
    client: AsyncClient, make_email: Callable[[], str]
) -> None:
    auth = await register_admin(client, make_email())
    tenant_id = await _tenant_id(client, auth)
    bot_id = await _create_bot(client, auth, allowed_domains=[_ACME_ORIGIN])
    body = {"bot_id": bot_id, "tenant_id": tenant_id}

    blocked = await client.post(
        "/api/widget/session", json=body, headers={"Origin": _EVIL_ORIGIN}
    )
    assert blocked.status_code == 403, blocked.text

    allowed = await client.post(
        "/api/widget/session", json=body, headers={"Origin": _ACME_ORIGIN}
    )
    assert allowed.status_code == 201, allowed.text


@pytest.mark.asyncio
async def test_widget_config_requires_token(client: AsyncClient) -> None:
    resp = await client.get("/api/widget/config")
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_widget_config_rejects_admin_token(
    client: AsyncClient, make_email: Callable[[], str]
) -> None:
    """An admin JWT must not be accepted on the widget plane (scope split)."""
    auth = await register_admin(client, make_email())
    resp = await client.get("/api/widget/config", headers=auth)
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_widget_config_returns_config(
    client: AsyncClient, make_email: Callable[[], str]
) -> None:
    auth = await register_admin(client, make_email())
    tenant_id = await _tenant_id(client, auth)
    bot_id = await _create_bot(client, auth)

    session = await client.post(
        "/api/widget/session",
        json={"bot_id": bot_id, "tenant_id": tenant_id},
    )
    token = session.json()["access_token"]

    resp = await client.get(
        "/api/widget/config", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["bot_id"] == bot_id


@pytest.mark.asyncio
async def test_preview_session_admin(
    client: AsyncClient, make_email: Callable[[], str]
) -> None:
    auth = await register_admin(client, make_email())
    bot_id = await _create_bot(client, auth)

    resp = await client.post(f"/api/bots/{bot_id}/preview-session", headers=auth)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["expires_in"] == 300

    claims = decode_token(data["access_token"], expected_scope="preview")
    assert claims["bot_id"] == bot_id

    # A preview token is accepted on the widget plane too.
    reuse = await client.get(
        "/api/widget/config",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert reuse.status_code == 200, reuse.text


@pytest.mark.asyncio
async def test_preview_session_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(f"/api/bots/{uuid.uuid4()}/preview-session")
    assert resp.status_code == 401, resp.text
