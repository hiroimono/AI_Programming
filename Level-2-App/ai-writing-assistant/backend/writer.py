# writer.py — AI Writing Service (SSE Streaming)
# =================================================
# Core service that communicates with OpenAI using streaming.
#
# .NET comparison:
#   This is like a service class that uses HttpClient to call
#   OpenAI's API with streaming enabled, yielding chunks as they arrive.

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
    messages: list[dict[str, str]], writing_mode: str = "general"
) -> AsyncGenerator[str, None]:
    """
    Streams AI response token-by-token using SSE format.

    .NET comparison:
      Like using IAsyncEnumerable<string> with yield return
      in a streaming endpoint.
    """
    system_prompt = WRITING_PROMPTS.get(writing_mode, WRITING_PROMPTS["general"])

    full_messages = [{"role": "system", "content": system_prompt}] + messages

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
