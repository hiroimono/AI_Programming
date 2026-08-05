"""Shared test fixtures.

Tests run against the REAL Neon dev DB. The app's import-time engine is bound
to the event loop that existed at import; pytest-asyncio spins up a fresh loop
per test, so reusing pooled asyncpg connections across tests fails with
"Event loop is closed". To avoid that we use a dedicated NullPool engine (no
connection is ever reused across loops) and override the `get_session`
dependency so the app never touches the global pooled engine during tests.

Every test uses a unique email prefixed with TEST_EMAIL_PREFIX; an autouse
fixture deletes those tenants afterwards so the DB stays clean.
"""

from __future__ import annotations

import uuid
from typing import AsyncIterator, Callable

import chatbot.chat as chat_module
import chatbot.pipeline as pipeline_module
import pytest_asyncio
from chatbot.config import get_settings
from chatbot.db import get_session, normalize_neon_url
from chatbot.main import app
from chatbot.models import AdminUser, Tenant
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_EMAIL_PREFIX = "m1test_"

_settings = get_settings()
_url, _connect_args = normalize_neon_url(
    _settings.database_url.get_secret_value()  # type: ignore[attr-defined]  # pylint: disable=no-member
)
# NullPool -> a brand new connection per checkout, closed immediately after.
# This makes the engine safe to use from a different event loop each test.
test_engine = create_async_engine(_url, poolclass=NullPool, connect_args=_connect_args)
TEST_SESSION = async_sessionmaker(test_engine, expire_on_commit=False)


async def _override_get_session() -> AsyncIterator:
    async with TEST_SESSION() as session:
        yield session


app.dependency_overrides[get_session] = _override_get_session

# The RAG pipeline opens its own sessions via db.session_factory (the global
# pooled engine bound to the import-time loop). pytest-asyncio uses a fresh
# loop per test, so reusing that pooled engine across tests raises
# "Event loop is closed". Rebind the pipeline's factory to the NullPool test
# sessionmaker so ingestion never touches the global pooled engine in tests.
pipeline_module.session_factory = TEST_SESSION

# The chat orchestrator (M5) opens its own sessions the same way; rebind it too.
chat_module.session_factory = TEST_SESSION

# Rate limiting is off for the bulk of the suite (tests fire many rapid
# register/login calls); the dedicated rate-limit test toggles it on locally.
from chatbot.ratelimit import limiter  # noqa: E402  pylint: disable=wrong-import-position

limiter.enabled = False


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


@pytest_asyncio.fixture
def make_email() -> Callable[[], str]:
    """Return a factory producing unique, cleanup-tagged test emails."""

    def _factory() -> str:
        return f"{TEST_EMAIL_PREFIX}{uuid.uuid4().hex}@example.com"

    return _factory


async def register_admin(http_client: AsyncClient, email: str) -> dict[str, str]:
    """Register a fresh tenant/admin and return its Bearer auth header."""
    resp = await http_client.post(
        "/api/auth/register",
        json={"tenant_name": "TestCo", "email": email, "password": "supersecret1"},
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest_asyncio.fixture
async def admin_auth(  # pylint: disable=redefined-outer-name
    client: AsyncClient, make_email: Callable[[], str]
) -> dict[str, str]:
    """Auth header for a single freshly-registered tenant admin."""
    return await register_admin(client, make_email())


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_test_tenants() -> AsyncIterator[None]:
    yield
    async with TEST_SESSION() as session:
        tenant_ids = (
            (
                await session.execute(
                    select(AdminUser.tenant_id).where(
                        AdminUser.email.like(f"{TEST_EMAIL_PREFIX}%")
                    )
                )
            )
            .scalars()
            .all()
        )
        if tenant_ids:
            # FK ondelete=CASCADE removes admin_users with the tenant.
            await session.execute(delete(Tenant).where(Tenant.id.in_(tenant_ids)))
            await session.commit()
