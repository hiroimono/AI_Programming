"""M2 bot CRUD + tenant isolation tests."""

from __future__ import annotations

import uuid
from typing import Callable

from httpx import AsyncClient
from tests.conftest import register_admin


async def _create_bot(
    client: AsyncClient, headers: dict[str, str], name: str = "Support"
) -> dict:
    resp = await client.post(
        "/api/bots",
        headers=headers,
        json={"name": name, "allowed_domains": ["https://acme.com"]},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_bot_seeds_default_config(
    client: AsyncClient, admin_auth: dict[str, str]
) -> None:
    bot = await _create_bot(client, admin_auth)
    assert bot["name"] == "Support"
    assert bot["status"] == "active"
    assert bot["allowed_domains"] == ["https://acme.com"]
    cfg = bot["config"]
    assert cfg is not None
    assert cfg["model"] == "gpt-4o-mini"
    assert cfg["temperature"] == 0.2
    assert cfg["primary_color"] == "#2563eb"
    assert cfg["suggested_questions"] == []


async def test_list_and_get_bot(
    client: AsyncClient, admin_auth: dict[str, str]
) -> None:
    bot = await _create_bot(client, admin_auth)

    listed = await client.get("/api/bots", headers=admin_auth)
    assert listed.status_code == 200
    ids = [b["id"] for b in listed.json()]
    assert bot["id"] in ids

    got = await client.get(f"/api/bots/{bot['id']}", headers=admin_auth)
    assert got.status_code == 200
    assert got.json()["id"] == bot["id"]


async def test_get_unknown_bot_404(
    client: AsyncClient, admin_auth: dict[str, str]
) -> None:
    resp = await client.get(f"/api/bots/{uuid.uuid4()}", headers=admin_auth)
    assert resp.status_code == 404


async def test_update_bot(client: AsyncClient, admin_auth: dict[str, str]) -> None:
    bot = await _create_bot(client, admin_auth)
    resp = await client.patch(
        f"/api/bots/{bot['id']}",
        headers=admin_auth,
        json={"name": "Renamed", "status": "disabled"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Renamed"
    assert body["status"] == "disabled"
    # Untouched field stays.
    assert body["allowed_domains"] == ["https://acme.com"]


async def test_update_bot_config(
    client: AsyncClient, admin_auth: dict[str, str]
) -> None:
    bot = await _create_bot(client, admin_auth)
    resp = await client.patch(
        f"/api/bots/{bot['id']}/config",
        headers=admin_auth,
        json={
            "welcome_message": "Merhaba!",
            "temperature": 0.7,
            "suggested_questions": ["Fiyat?", "Teslimat?"],
        },
    )
    assert resp.status_code == 200
    cfg = resp.json()
    assert cfg["welcome_message"] == "Merhaba!"
    assert cfg["temperature"] == 0.7
    assert cfg["suggested_questions"] == ["Fiyat?", "Teslimat?"]
    # Untouched default stays.
    assert cfg["model"] == "gpt-4o-mini"


async def test_delete_bot(client: AsyncClient, admin_auth: dict[str, str]) -> None:
    bot = await _create_bot(client, admin_auth)
    resp = await client.delete(f"/api/bots/{bot['id']}", headers=admin_auth)
    assert resp.status_code == 204
    gone = await client.get(f"/api/bots/{bot['id']}", headers=admin_auth)
    assert gone.status_code == 404


async def test_invalid_temperature_422(
    client: AsyncClient, admin_auth: dict[str, str]
) -> None:
    bot = await _create_bot(client, admin_auth)
    resp = await client.patch(
        f"/api/bots/{bot['id']}/config",
        headers=admin_auth,
        json={"temperature": 5},
    )
    assert resp.status_code == 422


async def test_create_requires_auth(client: AsyncClient) -> None:
    resp = await client.post("/api/bots", json={"name": "X"})
    assert resp.status_code == 401


async def test_tenant_isolation(
    client: AsyncClient, make_email: Callable[[], str]
) -> None:
    """Tenant B must not see or touch tenant A's bot (RLS boundary)."""
    a_headers = await register_admin(client, make_email())
    b_headers = await register_admin(client, make_email())

    a_bot = await _create_bot(client, a_headers, name="A-secret")

    # B's list is empty of A's bot.
    b_list = await client.get("/api/bots", headers=b_headers)
    assert b_list.status_code == 200
    assert all(b["id"] != a_bot["id"] for b in b_list.json())

    # B cannot read / update / delete A's bot -> 404 (not 403, to avoid
    # confirming the id exists).
    assert (
        await client.get(f"/api/bots/{a_bot['id']}", headers=b_headers)
    ).status_code == 404
    assert (
        await client.patch(
            f"/api/bots/{a_bot['id']}", headers=b_headers, json={"name": "hijack"}
        )
    ).status_code == 404
    assert (
        await client.delete(f"/api/bots/{a_bot['id']}", headers=b_headers)
    ).status_code == 404

    # A still sees its bot intact.
    a_get = await client.get(f"/api/bots/{a_bot['id']}", headers=a_headers)
    assert a_get.status_code == 200
    assert a_get.json()["name"] == "A-secret"
