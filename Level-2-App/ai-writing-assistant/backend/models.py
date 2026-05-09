# models.py — Pydantic Models (DTOs)
# ====================================

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    writing_mode: str = "general"  # general, blog, email, report, creative


class HealthResponse(BaseModel):
    status: str
    service: str
