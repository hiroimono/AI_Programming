"""Configuration loaded from environment / .env.

Uses pydantic-settings so types are validated at startup. Adding a new
setting later is a one-liner here plus a line in .env.example.
"""

from __future__ import annotations

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
                import json  # local import; rarely used
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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton. Import-safe; reads .env once."""
    return Settings()

