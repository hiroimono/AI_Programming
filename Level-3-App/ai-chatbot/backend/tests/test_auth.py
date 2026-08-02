"""M1 auth plane tests: register -> login -> me, plus failure paths."""

from __future__ import annotations

from typing import Callable

from chatbot.security import create_token
from httpx import AsyncClient

PASSWORD = "supersecret1"


async def _register(client: AsyncClient, email: str) -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"tenant_name": "Acme Ltd", "email": email, "password": PASSWORD},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_register_returns_token(
    client: AsyncClient, make_email: Callable[[], str]
) -> None:
    body = await _register(client, make_email())
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["expires_in"] > 0


async def test_duplicate_email_conflicts(
    client: AsyncClient, make_email: Callable[[], str]
) -> None:
    email = make_email()
    await _register(client, email)
    resp = await client.post(
        "/api/auth/register",
        json={"tenant_name": "Other", "email": email, "password": PASSWORD},
    )
    assert resp.status_code == 409


async def test_login_and_me_happy_path(
    client: AsyncClient, make_email: Callable[[], str]
) -> None:
    email = make_email()
    await _register(client, email)

    login = await client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.text
    data = me.json()
    assert data["admin"]["email"] == email
    assert data["admin"]["role"] == "owner"
    assert data["tenant"]["name"] == "Acme Ltd"
    assert data["admin"]["tenant_id"] == data["tenant"]["id"]


async def test_login_wrong_password_401(
    client: AsyncClient, make_email: Callable[[], str]
) -> None:
    email = make_email()
    await _register(client, email)
    resp = await client.post(
        "/api/auth/login", json={"email": email, "password": "wrong-password"}
    )
    assert resp.status_code == 401


async def test_login_unknown_email_401(
    client: AsyncClient, make_email: Callable[[], str]
) -> None:
    resp = await client.post(
        "/api/auth/login", json={"email": make_email(), "password": PASSWORD}
    )
    assert resp.status_code == 401


async def test_me_without_token_401(client: AsyncClient) -> None:
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


async def test_me_garbage_token_401(client: AsyncClient) -> None:
    resp = await client.get(
        "/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert resp.status_code == 401


async def test_me_wrong_scope_401(client: AsyncClient) -> None:
    # Valid signature but scope="widget" must be rejected by the admin guard.
    token, _ = create_token(
        subject="00000000-0000-0000-0000-000000000000",
        scope="widget",
        ttl_seconds=60,
        extra_claims={"tenant_id": "00000000-0000-0000-0000-000000000000"},
    )
    resp = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 401


async def test_me_expired_token_401(client: AsyncClient) -> None:
    token, _ = create_token(
        subject="00000000-0000-0000-0000-000000000000",
        scope="admin",
        ttl_seconds=-10,
        extra_claims={
            "tenant_id": "00000000-0000-0000-0000-000000000000",
            "role": "owner",
        },
    )
    resp = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 401
