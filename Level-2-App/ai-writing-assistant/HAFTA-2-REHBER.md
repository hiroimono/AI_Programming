# Hafta 2: SSE Streaming + Gerçek Zamanlı Chat Uygulaması

## 🎯 Bu Hafta Ne Yaptık?

**Uygulama:** AI Writing Assistant — Gerçek zamanlı yapay zeka yazım asistanı

Hafta 1'de "istek gönder → cevap bekle → sonucu göster" yapıyorduk. Bu hafta ise:

- Cevap **token token** (kelime kelime) akıyor — tıpkı ChatGPT gibi
- **Server-Sent Events (SSE)** protokolü kullanılıyor
- **5 farklı yazım modu:** General, Blog, Email, Report, Creative
- Konuşma geçmişi tutularak **bağlam farkındalığı** sağlanıyor
- Angular **Signals** ile reaktif UI

Hafta 1'deki tek seferlik "analiz et" butonu yerine, bu hafta canlı, akan bir sohbet deneyimi inşa ettik.

---

## 📐 Mimari

```
┌──────────────────┐     fetch + SSE      ┌──────────────────┐     Streaming      ┌──────────┐
│   Angular App    │ ───────────────────►  │   FastAPI         │ ──────────────────► │  OpenAI  │
│   (localhost:    │ ◄─ token token ────── │   Backend         │ ◄── chunk chunk ── │  GPT-4o  │
│    4201)         │   text/event-stream   │   (localhost:     │     stream=True    │  mini    │
│                  │                       │    8001)          │                    │          │
└──────────────────┘                       └──────────────────┘                    └──────────┘
```

**SSE Akışı:**

1. Angular `fetch()` ile POST isteği gönderir
2. FastAPI bağlantıyı açık tutar (`StreamingResponse`)
3. OpenAI'dan gelen her token `data: {"content": "kelime"}\n\n` formatında iletilir
4. Angular `ReadableStream` ile satır satır okur, RxJS Observable'a sarar
5. Son mesaj: `data: [DONE]\n\n` → stream tamamlandı

---

## 🔑 Hafta 1 vs Hafta 2: Temel Farklar

| Özellik            | Hafta 1 (Classifier)               | Hafta 2 (Writer)                    |
| ------------------ | ---------------------------------- | ----------------------------------- |
| İletişim           | Tek seferlik HTTP POST/Response    | SSE Streaming (sürekli bağlantı)    |
| OpenAI çağrısı     | `client.chat.completions.create()` | `create(stream=True)` + `async for` |
| Angular HTTP       | `HttpClient.post()`                | `fetch()` + `ReadableStream` → RxJS |
| Kullanıcı deneyimi | Bekle → sonucu gör                 | Token token akan metin              |
| Veri formatı       | JSON response                      | `text/event-stream` (SSE)           |
| Konuşma            | Tek mesaj                          | Çoklu mesaj geçmişi                 |
| Port               | Backend: 8000, Frontend: 4200      | Backend: 8001, Frontend: 4201       |

---

## 📁 Proje Yapısı

```
Level-2-App/ai-writing-assistant/
├── backend/
│   ├── main.py              ← FastAPI giriş noktası + SSE endpoint
│   ├── models.py            ← Pydantic modelleri (ChatMessage, ChatRequest)
│   ├── writer.py            ← OpenAI streaming servisi + yazım modları
│   ├── config.py            ← .env'den API key okuma
│   ├── requirements.txt     ← Python bağımlılıkları
│   ├── .env                 ← API anahtarı (git'e dahil DEĞİL)
│   └── venv/                ← Sanal ortam (git'e dahil DEĞİL)
│
└── frontend/                ← Angular 21 + Angular Material
    └── src/
        ├── environments/
        │   ├── environment.ts       ← Dev ayarları (localhost:8001)
        │   └── environment.prod.ts  ← Prod ayarları (Gateway URL)
        └── app/
            ├── app.config.ts        ← Angular providers
            ├── app.routes.ts        ← Lazy-loaded route
            ├── chat/
            │   ├── chat.component.ts    ← Chat mantığı (Signals)
            │   ├── chat.component.html  ← Chat UI template
            │   └── chat.component.scss  ← Dark glassmorphism tema
            └── services/
                └── chat.service.ts      ← SSE streaming servisi
```

---

## 🧠 Temel Kavramlar

### 1. Server-Sent Events (SSE) Nedir?

SSE, sunucudan istemciye **tek yönlü** veri akışı sağlayan bir HTTP protokolüdür.

| Özellik  | Normal HTTP         | SSE                        | WebSocket            |
| -------- | ------------------- | -------------------------- | -------------------- |
| Yön      | İstek → Yanıt (tek) | Sunucu → İstemci (sürekli) | Çift yönlü           |
| Bağlantı | Her istekte yeni    | Açık kalır                 | Açık kalır           |
| Protokol | HTTP                | HTTP                       | WS (farklı protokol) |
| Kullanım | API çağrıları       | AI streaming, bildirimler  | Chat, oyunlar        |

**SSE Mesaj Formatı:**

```
data: {"content": "Merhaba"}\n\n
data: {"content": " dünya"}\n\n
data: [DONE]\n\n
```

Her mesaj `data:` ile başlar ve iki newline (`\n\n`) ile biter.

**.NET Karşılaştırması:**

```csharp
// .NET'te SSE:
app.MapPost("/api/chat", async (HttpContext ctx) => {
    ctx.Response.ContentType = "text/event-stream";
    await foreach (var chunk in aiService.StreamAsync(request))
        await ctx.Response.WriteAsync($"data: {chunk}\n\n");
});
```

```python
# Python/FastAPI'de SSE:
@app.post("/api/chat")
async def chat_stream(request: ChatRequest):
    async def event_generator():
        async for token in stream_chat(messages):
            yield f"data: {json.dumps({'content': token})}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### 2. OpenAI Streaming API

Hafta 1'de `stream=False` (varsayılan) kullanıyorduk — tüm cevap bir anda geliyordu. Bu hafta `stream=True` ile token token alıyoruz:

```python
# Hafta 1 — Tek seferlik yanıt
response = await client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages,
)
full_text = response.choices[0].message.content

# Hafta 2 — Streaming yanıt
stream = await client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages,
    stream=True,  # ← Bu parametre farkı yaratıyor
)
async for chunk in stream:
    token = chunk.choices[0].delta.content  # Her seferinde 1-2 kelime
    if token:
        yield token
```

**`delta` vs `message`:**

- `stream=False` → `response.choices[0].message.content` (tüm metin)
- `stream=True` → `chunk.choices[0].delta.content` (parça parça)

### 3. Python AsyncGenerator

Python'da `async def` + `yield` kombinasyonu bir **async generator** oluşturur. Bu, .NET'teki `IAsyncEnumerable<T>` ile aynı konsept:

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

Signals, Angular'ın yeni reaktif ilkel yapısıdır. `BehaviorSubject` yerine daha basit bir API sunar:

```typescript
// Eski yöntem (BehaviorSubject)
messages$ = new BehaviorSubject<ChatMessage[]>([])
isStreaming$ = new BehaviorSubject<boolean>(false)

// Template'de: *ngIf="isStreaming$ | async"
// Güncellemede: this.messages$.next([...this.messages$.value, newMsg]);

// Yeni yöntem (Signals) ← Bu projede kullandığımız
messages = signal<ChatMessage[]>([])
isStreaming = signal(false)

// Template'de: @if (isStreaming()) { ... }
// Güncellemede: this.messages.update(msgs => [...msgs, newMsg]);
```

**Signal avantajları:**

- `async` pipe'a gerek yok
- Zone.js'e bağımlılık azalıyor
- `update()` ile fonksiyonel güncelleme — immutability korunuyor

### 5. fetch() + ReadableStream (Angular'da SSE)

Angular'ın `HttpClient`'ı SSE streaming için uygun değil çünkü tüm yanıtı bekler. Bunun yerine browser'ın native `fetch()` API'sini RxJS Observable ile sardık:

```typescript
streamChat(messages: ChatMessage[], writingMode: WritingMode): Observable<string> {
  return new Observable<string>((subscriber) => {
    const abortController = new AbortController();

    fetch(`${this.apiUrl}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages, writing_mode: writingMode }),
      signal: abortController.signal,   // ← İptal mekanizması
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
          buffer = lines.pop() ?? '';  // Son eksik satırı buffer'da tut

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);     // "data: " kısmını kes
              if (data === '[DONE]') {
                subscriber.complete();        // Stream bitti
                return;
              }
              const parsed = JSON.parse(data);
              subscriber.next(parsed.content); // Token'ı emit et
            }
          }
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError')
          subscriber.error(err);
      });

    // Unsubscribe olunca fetch'i iptal et
    return () => abortController.abort();
  });
}
```

**Kritik detaylar:**

- **Buffer mekanizması:** TCP paketleri satır sınırlarına göre bölünmez. `buffer` ile eksik satırlar bir sonraki `read()` ile birleştirilir
- **AbortController:** Observable unsubscribe olunca fetch isteği iptal edilir (bellek sızıntısı önlenir)
- **`{ stream: true }`:** TextDecoder'a "daha fazla veri gelecek" sinyali verir

### 6. Yazım Modları (System Prompts)

Her yazım modu, OpenAI'a farklı bir **system prompt** gönderir:

```python
WRITING_PROMPTS = {
    "general": "You are a helpful AI writing assistant...",
    "blog":    "You are a professional blog writer...",
    "email":   "You are a professional email writer...",
    "report":  "You are a technical report writer...",
    "creative":"You are a creative writer...",
}
```

System prompt, AI'ın "kişiliğini" ve yazım tarzını belirler. Kullanıcı modu değiştirince, aynı soru farklı tarzda cevaplanır.

---

## 🔧 Dosya Dosya Detaylı Açıklama

### Backend: `config.py`

```python
import os
from dotenv import load_dotenv

load_dotenv()  # .env dosyasını oku → ortam değişkenlerine yükle

class Settings:
    def __init__(self):
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        self.openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def validate(self) -> bool:
        return bool(self.openai_api_key)

settings = Settings()  # Singleton — tüm uygulama boyunca tek instance
```

.NET karşılığı: `appsettings.json` + `IOptions<T>` pattern. Python'da `.env` dosyasından `os.getenv()` ile okunur.

### Backend: `models.py`

```python
from pydantic import BaseModel

class ChatMessage(BaseModel):
    role: str       # "user" | "assistant" | "system"
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]        # Konuşma geçmişi
    writing_mode: str = "general"      # Varsayılan mod

class HealthResponse(BaseModel):
    status: str
    service: str
```

Hafta 1'den fark: Tek bir `text` yerine `messages` listesi gönderiyoruz → konuşma geçmişi.

### Backend: `writer.py`

OpenAI ile iletişim kuran servis. `stream=True` ile streaming yanıt alıp, `async for` ile token token yield ediyor.

```python
async def stream_chat(messages, writing_mode="general") -> AsyncGenerator[str, None]:
    system_prompt = WRITING_PROMPTS.get(writing_mode, WRITING_PROMPTS["general"])
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    stream = await client.chat.completions.create(
        model=settings.openai_model,
        messages=full_messages,
        stream=True,
        temperature=0.7,     # Yaratıcılık seviyesi (0=katı, 1=yaratıcı)
        max_tokens=2048,     # Maksimum yanıt uzunluğu
    )

    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
```

### Backend: `main.py`

FastAPI uygulaması. SSE endpoint'i `StreamingResponse` ile çalışır:

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

**CORS ayarı** — hangi origin'lerin istek atabileceğini belirler:

```python
allow_origins=["http://localhost:4200", "http://localhost:4201", "http://localhost:5000"]
```

### Frontend: `chat.service.ts`

SSE streaming'i RxJS Observable ile saran servis. `fetch()` + `ReadableStream` kullanır. Detaylı açıklama yukarıdaki "fetch() + ReadableStream" bölümünde.

### Frontend: `chat.component.ts`

Chat bileşeninin mantığı. Angular Signals kullanır:

```typescript
messages = signal<ChatMessage[]>([]) // Mesaj listesi
isStreaming = signal(false) // Akış devam ediyor mu?
writingMode = signal<WritingMode>('general') // Seçili yazım modu
```

**`sendMessage()` akışı:**

1. Kullanıcı mesajını listeye ekle
2. Boş bir assistant mesajı ekle (stream ile doldurulacak)
3. `chatService.streamChat()` çağır
4. Her `next(token)` geldiğinde, son mesajın `content`'ine ekle
5. `complete()` geldiğinde `isStreaming = false`

### Frontend: `chat.component.scss`

Dark tema + glassmorphism efektleri:

- Arka plan: `#0f0f1a` (koyu lacivert)
- Kullanıcı baloncukları: `linear-gradient(135deg, #6c63ff, #48c6ef)` (mor→mavi)
- Asistan baloncukları: `rgba(255, 255, 255, 0.06)` (yarı saydam cam)
- Scrollbar, Material overrides

---

## ⚙️ Nasıl Çalıştırılır?

### Backend

```powershell
cd Level-2-App/ai-writing-assistant/backend
& ./venv/Scripts/Activate.ps1
uvicorn main:app --reload --port 8001
```

- `--reload`: Kod değişince otomatik yeniden başlar
- `--port 8001`: Hafta 1 (8000) ile çakışmasın

### Frontend

```powershell
cd Level-2-App/ai-writing-assistant/frontend
ng serve --port 4201
```

Tarayıcıda `http://localhost:4201` aç.

### Sağlık Kontrolü

```powershell
curl http://localhost:8001/api/health
# → {"status":"healthy","service":"ai-writing-assistant"}
```

---

## 🏗️ Gateway Entegrasyonu (Sonraki Adım)

Production'da tüm istekler Gateway (.NET YARP) üzerinden geçecek:

```
Angular → Gateway (port 5000) → /apps/writer/api/* → FastAPI (port 8001)
```

`environment.ts`'de `gatewayUrl` ayarlandığında `chat.service.ts` otomatik olarak Gateway URL'ini kullanır:

```typescript
private apiUrl = environment.gatewayUrl
    ? `${environment.gatewayUrl}/apps/writer/api`
    : environment.apiUrl;
```

---

## 📝 Öğrenilen Dersler

1. **CORS:** Frontend port'unu (4201) CORS `allow_origins` listesine eklemeyi unutma — aksi halde preflight `OPTIONS` isteği 400 döner
2. **SSE buffer:** TCP paketleri satır sınırlarına göre bölünmez, buffer mekanizması şart
3. **AbortController:** Kullanıcı sayfadan çıkarsa veya yeni istek atarsa eski fetch iptal edilmeli
4. **Signals vs BehaviorSubject:** Angular 16+ için Signals çok daha temiz ve performanslı
5. **`stream=True`:** OpenAI'dan `delta.content` gelir (`message.content` değil)
