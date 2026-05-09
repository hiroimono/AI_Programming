# config.py — Configuration Management
# ======================================
# Reads settings from .env file.

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self):
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        self.openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def validate(self) -> bool:
        return bool(self.openai_api_key)


settings = Settings()
