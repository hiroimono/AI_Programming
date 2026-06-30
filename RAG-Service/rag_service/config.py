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
    service_name: str = Field(default="rag-service")
    environment: str = Field(default="development")

    # ─── HTTP ───────────────────────────────────────────────────────
    # Annotated[..., NoDecode] tells pydantic-settings to skip its default
    # JSON decoding for complex types — otherwise an empty `CORS_ORIGINS=`
    # in .env crashes with JSONDecodeError before our validator runs.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        description="Empty by default; only the consuming app backends "
        "talk to rag-service, not browsers.",
    )

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

    # ─── Database (Neon PostgreSQL) ─────────────────────────────────
    # SecretStr ensures the password is masked in logs and reprs.
    # Format: postgresql+asyncpg://user:pwd@host/dbname  (NO ?sslmode=...,
    # asyncpg uses `ssl=` kwarg instead — we strip the query string in db.py).
    database_url: SecretStr = Field(
        default=SecretStr(""),
        description="Neon connection string for rag_service_user.",
    )

    # Connection pool sizing. Neon free tier has tight connection limits;
    # keep these small. Bump in production.
    db_pool_size: int = Field(default=5)
    db_max_overflow: int = Field(default=2)

    # ─── OpenAI (embeddings + chat) ────────────────────────
    # SecretStr keeps the key out of logs / pydantic reprs / error messages.
    # Used by embedder.py for text-embedding-3-small (1536-dim vectors).
    openai_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="OpenAI API key (sk-proj-... or sk-...).",
    )

    # Embedding model and dimension are pinned here so chunker/embedder/
    # DB schema stay in sync. Changing the model later means a migration
    # (vector dim) and re-embedding all chunks.
    openai_embedding_model: str = Field(default="text-embedding-3-small")
    openai_embedding_dim: int = Field(default=1536)

    # ─── Storage (uploaded files) ──────────────────────────
    # Local FS backend for MVP. Stored relative to this directory.
    # Cloud backends (R2, Hetzner Object Storage) plug in later via
    # storage.py's backend abstraction without touching callers.
    storage_backend: str = Field(default="local")
    storage_local_path: str = Field(default="./storage")

    # ─── Internal service-to-service auth (JWT) ───────────────
    # Shared HMAC secret between rag-service and consuming app backends
    # (Level-2 writer backend, Level-3 chatbot backend). Tokens are
    # short-lived (~5 min); rag-service does not mint tokens, only verifies.
    # In production this should be 32+ random bytes; generate with
    #   python -c "import secrets; print(secrets.token_urlsafe(32))"
    internal_jwt_secret: SecretStr = Field(
        default=SecretStr(""),
        description="HMAC secret for verifying internal JWT bearer tokens.",
    )
    internal_jwt_algorithm: str = Field(default="HS256")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton. Import-safe; reads .env once."""
    return Settings()
