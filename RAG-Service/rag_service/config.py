"""Configuration loaded from environment / .env.

Uses pydantic-settings so types are validated at startup. Adding a new
setting later is a one-liner here plus a line in .env.example.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    cors_origins: list[str] = Field(
        default_factory=list,
        description="Empty by default; only the consuming app backends "
        "talk to rag-service, not browsers.",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton. Import-safe; reads .env once."""
    return Settings()
