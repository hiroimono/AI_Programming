# config.py — Configuration Management
# ======================================
# Equivalent of IConfiguration + appsettings.json in .NET.
# Reads settings from .env file and makes them type-safe.

import os
from dotenv import load_dotenv

# Read .env file (think of it as reading from appsettings.json)
load_dotenv()


class Settings:
    """
    Python equivalent of the IOptions<T> pattern in .NET.
    All configuration in one place, type-safe.
    """

    def __init__(self):
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        self.openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        # Azure OpenAI support (optional)
        self.azure_openai_endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        self.azure_openai_key: str = os.getenv("AZURE_OPENAI_KEY", "")
        self.azure_openai_deployment: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")

    @property
    def use_azure(self) -> bool:
        """Whether to use Azure OpenAI or direct OpenAI API."""
        return bool(self.azure_openai_endpoint and self.azure_openai_key)


# Singleton instance — use `from config import settings` everywhere
settings = Settings()
