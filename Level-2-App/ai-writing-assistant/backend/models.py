# models.py — Pydantic Models (DTOs)
# ====================================

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    writing_mode: str = "general"  # general, blog, email, report, creative


class GenerateTitleRequest(BaseModel):
    messages: list[ChatMessage]
    current_title: str = ""


class GenerateTitleResponse(BaseModel):
    title: str
    new_score: int  # 0-100 relevance score for the new title
    old_score: int  # 0-100 relevance score for the current title


class HealthResponse(BaseModel):
    status: str
    service: str
