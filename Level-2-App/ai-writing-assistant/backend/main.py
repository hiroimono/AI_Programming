# main.py — FastAPI Application Entry Point (SSE Streaming)
# ============================================================
# Equivalent of Program.cs in .NET.
#
# Key concept: Server-Sent Events (SSE)
# ─────────────────────────────────────
# SSE is a one-way streaming protocol (server → client) over HTTP.
# Unlike WebSocket (bidirectional), SSE uses a standard GET/POST request
# and the server keeps the connection open, pushing "events" as they arrive.
#
# Format: each event is "data: <content>\n\n"
# End signal: "data: [DONE]\n\n"
#
# .NET comparison:
#   app.MapPost("/api/chat", async (HttpContext ctx) => {
#       ctx.Response.ContentType = "text/event-stream";
#       await foreach (var chunk in aiService.StreamAsync(request))
#           await ctx.Response.WriteAsync($"data: {chunk}\n\n");
#   });

import json

from config import settings
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from models import ChatRequest, HealthResponse
from writer import stream_chat

app = FastAPI(
    title="AI Writing Assistant",
    description="SSE Streaming AI Writing Service",
    version="1.0.0",
)

# CORS — Allow Gateway and local Angular dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://localhost:4201",
        "http://localhost:5000",
        "https://gateway-production-072b.up.railway.app",
        "https://ai-programming.pages.dev",
        "https://ai-writing-assistant.pages.dev",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="healthy", service="ai-writing-assistant")


@app.post("/api/chat")
async def chat_stream(request: ChatRequest):
    """
    SSE streaming chat endpoint.

    The client sends conversation history + writing mode,
    and receives tokens streamed back in real-time.

    Response format: text/event-stream
      data: {"content": "Hello"}
      data: {"content": " world"}
      data: [DONE]
    """
    if not settings.validate():
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    async def event_generator():
        async for token in stream_chat(messages, request.writing_mode):
            # SSE format: "data: <json>\n\n"
            yield f"data: {json.dumps({'content': token})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering if proxied
        },
    )
