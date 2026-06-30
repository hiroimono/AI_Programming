# config.py — Configuration Management
# ======================================
# Reads settings from .env file.

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self):
        # --- OpenAI ---
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        self.openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        # --- Gateway JWT (Phase 5) ---
        # Used to verify the user's Bearer token forwarded by the Gateway.
        # Must match Gateway's Jwt:Secret. If empty, auth-required endpoints
        # (document upload/list/delete) refuse to start; /api/chat keeps
        # working in anonymous mode for local dev without the Gateway.
        self.gateway_jwt_secret: str = os.getenv("GATEWAY_JWT_SECRET", "")
        self.gateway_jwt_issuer: str = os.getenv("GATEWAY_JWT_ISSUER", "Gateway.API")
        self.gateway_jwt_audience: str = os.getenv(
            "GATEWAY_JWT_AUDIENCE", "Gateway.Clients"
        )

        # --- rag-service (Phase 5) ---
        # Base URL of the central rag-service. Used by rag_client.
        self.rag_service_url: str = os.getenv(
            "RAG_SERVICE_URL", "http://localhost:8100"
        )
        # Shared HS256 secret used to mint internal JWTs for rag-service.
        # Must match rag-service's INTERNAL_JWT_SECRET.
        self.rag_internal_jwt_secret: str = os.getenv("RAG_INTERNAL_JWT_SECRET", "")
        # App id we send in the internal JWT. rag-service maps this to
        # the level2 schema.
        self.rag_app_id: str = os.getenv("RAG_APP_ID", "level-2-writer")

    def validate(self) -> bool:
        """Minimal sanity check: chat works as long as OpenAI is configured."""
        return bool(self.openai_api_key)

    def rag_enabled(self) -> bool:
        """True when both Gateway auth and rag-service config are present.

        When False, document endpoints return 503 and /api/chat falls back
        to plain (non-RAG) behavior.
        """
        return bool(self.gateway_jwt_secret) and bool(self.rag_internal_jwt_secret)


settings = Settings()
