# Week 2: SSE Streaming + Real-Time Chat Application

## 🎯 What Did We Build This Week?

**Application:** AI Writing Assistant — Real-time AI-powered writing assistant

In Week 1, we followed a "send request → wait → show result" pattern. This week:

- Response streams **token by token** — just like ChatGPT
- Uses the **Server-Sent Events (SSE)** protocol
- **5 writing modes:** General, Blog, Email, Report, Creative
- **Context awareness** via conversation history
- Reactive UI with Angular **Signals**

Instead of Week 1's one-shot "Analyze" button, we built a live, streaming chat experience.

---

## 📐 Architecture

```
┌──────────────────┐     fetch + SSE      ┌──────────────────┐     Streaming      ┌──────────┐
│   Angular App    │ ───────────────────►  │   FastAPI         │ ──────────────────► │  OpenAI  │
│   (localhost:    │ ◄─ token token ────── │   Backend         │ ◄── chunk chunk ── │  GPT-4o  │
│    4201)         │   text/event-stream   │   (localhost:     │     stream=True    │  mini    │
│                  │                       │    8001)          │                    │          │
└──────────────────┘                       └──────────────────┘                    └──────────┘
```

**SSE Flow:**

1. Angular sends a POST request using `fetch()`
2. FastAPI keeps the connection open (`StreamingResponse`)
3. Each token from OpenAI is forwarded as `data: {"content": "word"}\n\n`
4. Angular reads the stream line-by-line via `ReadableStream`, wrapped in an RxJS Observable
5. Final message: `data: [DONE]\n\n` → stream complete

---

## 🔑 Week 1 vs Week 2: Key Differences

| Feature         | Week 1 (Classifier)                | Week 2 (Writer)                       |
| --------------- | ---------------------------------- | ------------------------------------- |
| Communication   | Single HTTP POST/Response          | SSE Streaming (persistent connection) |
| OpenAI call     | `client.chat.completions.create()` | `create(stream=True)` + `async for`   |
| Angular HTTP    | `HttpClient.post()`                | `fetch()` + `ReadableStream` → RxJS   |
| User experience | Wait → see result                  | Text flowing token by token           |
| Data format     | JSON response                      | `text/event-stream` (SSE)             |
| Conversation    | Single message                     | Multi-message history                 |
| Ports           | Backend: 8000, Frontend: 4200      | Backend: 8001, Frontend: 4201         |

---

## 📁 Project Structure

```
Level-2-App/ai-writing-assistant/
├── backend/
│   ├── main.py              ← FastAPI entry point + SSE endpoint
│   ├── models.py            ← Pydantic models (ChatMessage, ChatRequest)
│   ├── writer.py            ← OpenAI streaming service + writing modes
│   ├── config.py            ← Reads API key from .env
│   ├── requirements.txt     ← Python dependencies
│   ├── .env                 ← API key (NOT in git)
│   └── venv/                ← Virtual environment (NOT in git)
│
└── frontend/                ← Angular 21 + Angular Material
    └── src/
        ├── environments/
        │   ├── environment.ts       ← Dev settings (localhost:8001)
        │   └── environment.prod.ts  ← Prod settings (Gateway URL)
        └── app/
            ├── app.config.ts        ← Angular providers
            ├── app.routes.ts        ← Lazy-loaded route
            ├── chat/
            │   ├── chat.component.ts    ← Chat logic (Signals)
            │   ├── chat.component.html  ← Chat UI template
            │   └── chat.component.scss  ← Dark glassmorphism theme
            └── services/
                └── chat.service.ts      ← SSE streaming service
```

---

## 🧠 Core Concepts

### 1. What is Server-Sent Events (SSE)?

SSE is an HTTP protocol for **one-way** data streaming from server to client.

| Feature    | Standard HTTP                 | SSE                          | WebSocket               |
| ---------- | ----------------------------- | ---------------------------- | ----------------------- |
| Direction  | Request → Response (one-shot) | Server → Client (continuous) | Bidirectional           |
| Connection | New per request               | Kept open                    | Kept open               |
| Protocol   | HTTP                          | HTTP                         | WS (different protocol) |
| Use case   | API calls                     | AI streaming, notifications  | Chat, games             |

**SSE Message Format:**

```
data: {"content": "Hello"}\n\n
data: {"content": " world"}\n\n
data: [DONE]\n\n
```

Each message starts with `data:` and ends with two newlines (`\n\n`).

**.NET Comparison:**

```csharp
// SSE in .NET:
app.MapPost("/api/chat", async (HttpContext ctx) => {
    ctx.Response.ContentType = "text/event-stream";
    await foreach (var chunk in aiService.StreamAsync(request))
        await ctx.Response.WriteAsync($"data: {chunk}\n\n");
});
```

```python
# SSE in Python/FastAPI:
@app.post("/api/chat")
async def chat_stream(request: ChatRequest):
    async def event_generator():
        async for token in stream_chat(messages):
            yield f"data: {json.dumps({'content': token})}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### 2. OpenAI Streaming API

In Week 1, we used `stream=False` (default) — the entire response arrived at once. This week, `stream=True` delivers tokens one by one:

```python
# Week 1 — Single response
response = await client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages,
)
full_text = response.choices[0].message.content

# Week 2 — Streaming response
stream = await client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages,
    stream=True,  # ← This parameter makes the difference
)
async for chunk in stream:
    token = chunk.choices[0].delta.content  # 1-2 words at a time
    if token:
        yield token
```

**`delta` vs `message`:**

- `stream=False` → `response.choices[0].message.content` (full text)
- `stream=True` → `chunk.choices[0].delta.content` (incremental)

### 3. Python AsyncGenerator

Combining `async def` with `yield` in Python creates an **async generator**. This is the same concept as .NET's `IAsyncEnumerable<T>`:

```csharp
// .NET IAsyncEnumerable
async IAsyncEnumerable<string> StreamTokens() {
    await foreach (var chunk in openAiStream) {
        yield return chunk.Content;
    }
}
```

```python
# Python AsyncGenerator
async def stream_chat(messages) -> AsyncGenerator[str, None]:
    stream = await client.chat.completions.create(stream=True, ...)
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
```

### 4. Angular Signals (Angular 16+)

Signals are Angular's new reactive primitive. They offer a simpler API than `BehaviorSubject`:

```typescript
// Old approach (BehaviorSubject)
messages$ = new BehaviorSubject<ChatMessage[]>([])
isStreaming$ = new BehaviorSubject<boolean>(false)

// In template: *ngIf="isStreaming$ | async"
// Updating: this.messages$.next([...this.messages$.value, newMsg]);

// New approach (Signals) ← Used in this project
messages = signal<ChatMessage[]>([])
isStreaming = signal(false)

// In template: @if (isStreaming()) { ... }
// Updating: this.messages.update(msgs => [...msgs, newMsg]);
```

**Signal advantages:**

- No need for `async` pipe
- Reduced Zone.js dependency
- Functional updates with `update()` — immutability preserved

### 5. fetch() + ReadableStream (SSE in Angular)

Angular's `HttpClient` isn't suitable for SSE streaming because it waits for the full response. Instead, we wrapped the browser's native `fetch()` API in an RxJS Observable:

```typescript
streamChat(messages: ChatMessage[], writingMode: WritingMode): Observable<string> {
  return new Observable<string>((subscriber) => {
    const abortController = new AbortController();

    fetch(`${this.apiUrl}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages, writing_mode: writingMode }),
      signal: abortController.signal,   // ← Cancellation mechanism
    })
      .then(async (response) => {
        const reader = response.body!.getReader();  // ← ReadableStream
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';  // Keep incomplete line in buffer

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);     // Strip "data: " prefix
              if (data === '[DONE]') {
                subscriber.complete();        // Stream finished
                return;
              }
              const parsed = JSON.parse(data);
              subscriber.next(parsed.content); // Emit the token
            }
          }
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError')
          subscriber.error(err);
      });

    // Cancel fetch on unsubscribe
    return () => abortController.abort();
  });
}
```

**Critical details:**

- **Buffer mechanism:** TCP packets don't split on line boundaries. The `buffer` joins incomplete lines with the next `read()` call
- **AbortController:** Cancels the fetch when the Observable is unsubscribed (prevents memory leaks)
- **`{ stream: true }`:** Tells TextDecoder "more data is coming"

### 6. Writing Modes (System Prompts)

Each writing mode sends a different **system prompt** to OpenAI:

```python
WRITING_PROMPTS = {
    "general": "You are a helpful AI writing assistant...",
    "blog":    "You are a professional blog writer...",
    "email":   "You are a professional email writer...",
    "report":  "You are a technical report writer...",
    "creative":"You are a creative writer...",
}
```

The system prompt defines the AI's "personality" and writing style. When the user switches modes, the same question gets answered in a different style.

---

## 🔧 File-by-File Detailed Breakdown

### Backend: `config.py`

```python
import os
from dotenv import load_dotenv

load_dotenv()  # Read .env file → load into environment variables

class Settings:
    def __init__(self):
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        self.openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def validate(self) -> bool:
        return bool(self.openai_api_key)

settings = Settings()  # Singleton — single instance throughout the app
```

.NET equivalent: `appsettings.json` + `IOptions<T>` pattern. In Python, values are read from `.env` via `os.getenv()`.

### Backend: `models.py`

```python
from pydantic import BaseModel

class ChatMessage(BaseModel):
    role: str       # "user" | "assistant" | "system"
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]        # Conversation history
    writing_mode: str = "general"      # Default mode

class HealthResponse(BaseModel):
    status: str
    service: str
```

Difference from Week 1: Instead of a single `text` field, we send a `messages` list → conversation history.

### Backend: `writer.py`

The service that communicates with OpenAI. Uses `stream=True` for streaming responses, yielding tokens via `async for`.

```python
async def stream_chat(messages, writing_mode="general") -> AsyncGenerator[str, None]:
    system_prompt = WRITING_PROMPTS.get(writing_mode, WRITING_PROMPTS["general"])
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    stream = await client.chat.completions.create(
        model=settings.openai_model,
        messages=full_messages,
        stream=True,
        temperature=0.7,     # Creativity level (0=strict, 1=creative)
        max_tokens=2048,     # Maximum response length
    )

    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
```

### Backend: `main.py`

The FastAPI application. The SSE endpoint uses `StreamingResponse`:

```python
@app.post("/api/chat")
async def chat_stream(request: ChatRequest):
    async def event_generator():
        async for token in stream_chat(messages, request.writing_mode):
            yield f"data: {json.dumps({'content': token})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

**CORS configuration** — defines which origins can make requests:

```python
allow_origins=["http://localhost:4200", "http://localhost:4201", "http://localhost:5000"]
```

### Frontend: `chat.service.ts`

The service that wraps SSE streaming in an RxJS Observable using `fetch()` + `ReadableStream`. See the detailed "fetch() + ReadableStream" section above.

### Frontend: `chat.component.ts`

The chat component's logic. Uses Angular Signals:

```typescript
messages = signal<ChatMessage[]>([]) // Message list
isStreaming = signal(false) // Is streaming in progress?
writingMode = signal<WritingMode>('general') // Selected writing mode
```

**`sendMessage()` flow:**

1. Add the user message to the list
2. Add an empty assistant message (will be filled by stream)
3. Call `chatService.streamChat()`
4. On each `next(token)`, append to the last message's `content`
5. On `complete()`, set `isStreaming = false`

### Frontend: `chat.component.scss`

Dark theme + glassmorphism effects:

- Background: `#0f0f1a` (deep navy)
- User bubbles: `linear-gradient(135deg, #6c63ff, #48c6ef)` (purple→blue)
- Assistant bubbles: `rgba(255, 255, 255, 0.06)` (semi-transparent glass)
- Custom scrollbar, Material overrides

---

## ⚙️ How to Run

### Backend

```powershell
cd Level-2-App/ai-writing-assistant/backend
& ./venv/Scripts/Activate.ps1
uvicorn main:app --reload --port 8001
```

- `--reload`: Auto-restarts on code changes
- `--port 8001`: Avoids conflict with Week 1 (port 8000)

### Frontend

```powershell
cd Level-2-App/ai-writing-assistant/frontend
ng serve --port 4201
```

Open `http://localhost:4201` in your browser.

### Health Check

```powershell
curl http://localhost:8001/api/health
# → {"status":"healthy","service":"ai-writing-assistant"}
```

---

## 🏗️ Gateway Integration (Next Step)

In production, all requests will go through the Gateway (.NET YARP):

```
Angular → Gateway (port 5000) → /apps/writer/api/* → FastAPI (port 8001)
```

When `gatewayUrl` is set in `environment.ts`, `chat.service.ts` automatically uses the Gateway URL:

```typescript
private apiUrl = environment.gatewayUrl
    ? `${environment.gatewayUrl}/apps/writer/api`
    : environment.apiUrl;
```

---

## 📝 Lessons Learned

1. **CORS:** Don't forget to add the frontend port (4201) to CORS `allow_origins` — otherwise the preflight `OPTIONS` request returns 400
2. **SSE buffer:** TCP packets don't split on line boundaries — a buffer mechanism is essential
3. **AbortController:** If the user navigates away or sends a new request, the old fetch must be cancelled
4. **Signals vs BehaviorSubject:** For Angular 16+, Signals are much cleaner and more performant
5. **`stream=True`:** OpenAI returns `delta.content` (not `message.content`)
