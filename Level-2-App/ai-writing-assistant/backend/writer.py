# writer.py — AI Writing Service (SSE Streaming)
# =================================================
# Core service that communicates with OpenAI using streaming.
#
# .NET comparison:
#   This is like a service class that uses HttpClient to call
#   OpenAI's API with streaming enabled, yielding chunks as they arrive.

import json
from collections.abc import AsyncGenerator

from config import settings
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=settings.openai_api_key)

# System prompts for different writing modes
WRITING_PROMPTS: dict[str, str] = {
    "general": "You are a helpful AI writing assistant. Respond clearly and concisely.",
    "blog": (
        "You are a professional blog writer. Write engaging, well-structured blog posts "
        "with clear headings, short paragraphs, and a conversational tone."
    ),
    "email": (
        "You are a professional email writer. Write clear, polite, and concise emails "
        "appropriate for business communication."
    ),
    "report": (
        "You are a technical report writer. Write formal, structured reports with "
        "clear sections, data-driven insights, and professional language."
    ),
    "creative": (
        "You are a creative writer. Write with vivid imagery, emotional depth, "
        "and engaging narrative techniques."
    ),
}


async def stream_chat(
    messages: list[dict[str, str]],
    writing_mode: str = "general",
    rag_context: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Streams AI response token-by-token using SSE format.

    .NET comparison:
      Like using IAsyncEnumerable<string> with yield return
      in a streaming endpoint.

    When `rag_context` is provided, it is injected as an additional
    system message right after the writing-mode system prompt. The model
    is told to ground answers in that context and to refuse when it
    isn't enough — this is the hallucination guard.
    """
    system_prompt = WRITING_PROMPTS.get(writing_mode, WRITING_PROMPTS["general"])

    full_messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    if rag_context:
        full_messages.append(
            {
                "role": "system",
                "content": (
                    "You have access to the following excerpts from the "
                    "user's uploaded documents. Ground your answer in them. "
                    "If the excerpts do not contain the answer, say so "
                    "explicitly instead of guessing. When you use a fact "
                    "from an excerpt, cite the source filename inline.\n\n"
                    f"--- BEGIN DOCUMENT CONTEXT ---\n{rag_context}\n"
                    "--- END DOCUMENT CONTEXT ---"
                ),
            }
        )
    full_messages.extend(messages)

    stream = await client.chat.completions.create(
        model=settings.openai_model,
        messages=full_messages,
        stream=True,
        temperature=0.7,
        max_tokens=2048,
    )

    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


async def generate_title(
    messages: list[dict[str, str]], current_title: str = ""
) -> dict:
    """
    Generates a concise conversation title using AI.
    Also scores both the new and current title for relevance (0-100).
    """
    conversation_text = "\n".join(
        f"{m['role']}: {m['content'][:300]}" for m in messages if m["role"] != "system"
    )

    scoring_instruction = ""
    if current_title:
        scoring_instruction = (
            f'\nThe current title is: "{current_title}"\n'
            "Score both titles for relevance to the conversation (0-100)."
        )

    prompt = (
        "Given the following conversation, generate a short, descriptive title "
        "(max 50 characters, no quotes).\n"
        "IMPORTANT: The title MUST be in the same language as the user's messages. "
        "If the user writes in Turkish, the title must be in Turkish. "
        "If the user writes in English, the title must be in English. "
        "Always match the user's language.\n"
        "Also evaluate how well the title reflects the LATEST topic of conversation."
        f"{scoring_instruction}\n\n"
        f"Conversation:\n{conversation_text}\n\n"
        'Respond ONLY with valid JSON: {"title": "...", "new_score": 85, "old_score": 60}\n'
        "If there is no current title, set old_score to 0.\n"
        "If the conversation topic has clearly changed from the current title, "
        "give old_score a low value (under 30)."
    )

    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=100,
    )

    raw = response.choices[0].message.content or "{}"

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"title": "New chat", "new_score": 50, "old_score": 0}

    return {
        "title": str(result.get("title", "New chat"))[:200],
        "new_score": int(result.get("new_score", 50)),
        "old_score": int(result.get("old_score", 0)),
    }
