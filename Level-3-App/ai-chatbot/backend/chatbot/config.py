"""Configuration loaded from environment / .env.

Uses pydantic-settings so types are validated at startup. Adding a new
setting later is a one-liner here plus a line in .env.example.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── Service identity ───────────────────────────────────────────
    service_name: str = Field(default="chatbot-service")
    environment: str = Field(default="development")

    # ─── HTTP / CORS ────────────────────────────────────────────────
    # Unlike rag-service, this API IS called from the browser (admin panel
    # + embeddable widget), so real origins must be allow-listed.
    # Annotated[..., NoDecode] skips pydantic-settings' default JSON decoding
    # so an empty `CORS_ORIGINS=` in .env does not crash before our validator.
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, raw: object) -> list[str]:
        """Accept three .env forms: empty, comma-separated, JSON array."""
        if raw is None or raw == "":
            return []
        if isinstance(raw, list):
            return raw
        if isinstance(raw, str):
            s = raw.strip()
            if s.startswith("["):
                return json.loads(s)
            return [piece.strip() for piece in s.split(",") if piece.strip()]
        raise TypeError(f"Unsupported CORS_ORIGINS value: {raw!r}")

    # ─── Database (Level-3 OWN Neon PostgreSQL) ─────────────────────
    # SecretStr keeps the password masked in logs and reprs.
    # Format: postgresql+asyncpg://user:pwd@host/dbname  (query string with
    # sslmode is stripped in db.py; asyncpg uses ssl= connect_arg instead).
    database_url: SecretStr = Field(default=SecretStr(""))

    # Connection pool sizing. Neon free tier has tight connection limits.
    db_pool_size: int = Field(default=5)
    db_max_overflow: int = Field(default=2)

    # ─── OpenAI (embeddings + chat) ─────────────────────────────────
    openai_api_key: SecretStr = Field(default=SecretStr(""))
    # Pinned so chunker/embedder/DB vector dim stay in sync. Changing the
    # embedding model later means a migration + re-embedding all chunks.
    openai_embedding_model: str = Field(default="text-embedding-3-small")
    openai_embedding_dim: int = Field(default=1536)
    openai_chat_model: str = Field(default="gpt-4o-mini")

    # ─── Storage (uploaded files) ───────────────────────────────────
    storage_backend: str = Field(default="local")
    storage_local_path: str = Field(default="./storage")

    # ─── Auth (JWT) ─────────────────────────────────────────────────
    # One HMAC secret signs all app-issued tokens; the `scope` claim
    # (admin | widget | preview) differentiates them. Can be split into
    # per-scope secrets later without touching callers.
    jwt_secret: SecretStr = Field(default=SecretStr(""))
    jwt_algorithm: str = Field(default="HS256")
    admin_token_ttl: int = Field(default=3600)
    widget_token_ttl: int = Field(default=86400)
    preview_token_ttl: int = Field(default=300)

    # ─── Rate limiting (M8) ─ technical abuse prevention ──────────
    # Per-client (IP) request caps enforced by slowapi. This is NOT
    # plan-based quota (free/paid monthly message limits) — that is a
    # future billing-phase feature keyed on Tenant.plan + UsageEvent.
    # Values use slowapi's "<count>/<period>" syntax and are tunable here.
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_login: str = Field(default="5/minute")
    rate_limit_register: str = Field(default="10/hour")
    rate_limit_widget_session: str = Field(default="10/minute")
    rate_limit_widget_chat: str = Field(default="30/minute")

    # ─── Content moderation (M8) ─ input screening ────────────────
    # Screen each incoming user message with OpenAI's free moderation
    # endpoint (omni-moderation-latest) BEFORE it reaches retrieval or the
    # LLM. Flagged turns are answered with a canned refusal (persisted for
    # audit) and never call the model. Fails open on provider error so a
    # moderation outage cannot take chat down.
    moderation_enabled: bool = Field(default=True)
    moderation_refusal_message: str = Field(
        default=(
            "I can't help with that request. Please rephrase it or ask "
            "something else."
        )
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton. Import-safe; reads .env once."""
    return Settings()
