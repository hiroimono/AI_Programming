# Level-3 Chatbot — Architecture and Decisions (Living Doc)

> **Purpose:** This file is the single source of truth for the project.
> Updated at the end of every milestone. If code and this doc disagree,
> **code wins** — but the disagreement is a signal to fix the doc.
> Last update: **end of M5** (chat SSE + RAG retrieval).

---

## 1. Product positioning (critical reframe)

| | Level-1 / Level-2 | **Level-3 (this project)** |
|---|---|---|
| Model | B2C, single user (behind Gateway) | **B2B2C, multi-tenant SaaS** |
| Customer | Individual | **Company (tenant)** |
| End user | The person who signs up | **Anonymous visitor** on the tenant's site |

**Consequence:** the Level-1/2 audience (individuals) ≠ the Level-3 audience
(companies) → the value of a "single identity" is lower than assumed. Level-3
carries its own control plane in the backend.

---

## 2. Locked forks (approved)

- **FORK A = A1** — Fully standalone. The Gateway is **not touched**. A separate
  **B2B CDN/gateway** may be added in front of Level-3 later (a product-facing
  layer, no business logic). Why: Level-3 is B2B; the Gateway's B2C control-plane
  logic moves to the backend here, so in the MVP the Gateway would be a mere
  dumb-passthrough (an unnecessary hop).
- **FORK B = B2** — Level-3 carries **its own RAG**, extending RAG-Service's proven
  structure (chunker/embedder/retriever/pgvector) **adapted to tenant/bot scope**,
  plus an **Embedder/Retriever Protocol seam**. The production RAG-Service is not
  touched (Level-2 depends on it).
- **Overall:** the thin-slice MVP is a self-contained vertical (A1 + B2), with seams
  ready for future consolidation.

---

## 3. Technology stack (lock-in)

**Backend:** FastAPI + **plain SQLAlchemy 2.0 async** (instead of the plan's SQLModel —
for code copy-adapt consistency with RAG-Service) + asyncpg + Alembic + PyJWT +
argon2-cffi + slowapi + pgvector.
**DB:** Neon PostgreSQL (EU), a **separate database `ai_chatbotdb`** inside the
`ai-platform` project / `production` branch, with a **dedicated owner role
`ai_chatbot_owner`** (credential isolation). Direct connection (pooler OFF).
**OpenAI:** project-scoped restricted key (`Model capabilities = Request`).
**Widget (M6):** Lit + Shadow DOM. **Admin panel (M7):** Angular.
**Tests:** pytest + pytest-asyncio + httpx ASGITransport (+ Playwright later).
**Dev port:** `8200` (RAG=8100, Level-2 BE=8001, Level-1 BE=8000).

---

## 4. Two auth planes

One `JWT_SECRET`, **HS256**. Differentiated by the `scope` claim.

| Scope | Who | TTL | Milestone |
|---|---|---|---|
| `admin` | Tenant administrator (panel) | 3600s (1h) | **M1 ✅** |
| `widget` | Anonymous visitor (embed) | 86400s (24h) | **M4 ✅** |
| `preview` | Admin live preview | 300s (5m) | **M4 ✅** |

**Token claims:** `sub`, `scope`, `iat`, `exp` + for admin: `tenant_id`, `role`.

`get_current_admin` (deps.py) is the **single seam**: decode token (scope=admin) →
**pin the RLS tenant GUC** → load the live `AdminUser` (id+tenant_id+is_active).
Every tenant-scoped handler depends on it → no handler can reach another tenant's data.

`get_current_widget` (deps.py) is the widget-plane seam: decode token (scope
`widget` or `preview`) → **pin the RLS tenant GUC from the token** → **no DB lookup**
(the signed token *is* the identity; RLS enforces tenant scope). `is_preview` is
derived from the scope so preview turns are excluded from usage accounting.

---

## 5. Row-Level Security (RLS) — the heart of isolation

- **7 tenant-scoped tables** with RLS ENABLE + **FORCE** (FORCE is required on a
  single-role Neon DB, otherwise the owner bypasses RLS): `bots, bot_configs,
  documents, chunks, conversations, messages, usage_events`.
- **Excluded from RLS:** `tenants`, `admin_users` (login/administration are
  cross-tenant control-plane operations).
- **Policy `tenant_isolation`** (on every table, both USING and WITH CHECK):
  `tenant_id = current_setting('app.current_tenant', true)::uuid`
  → if the GUC is unset, `current_setting` returns NULL → no row is visible/writable.
- **Setting the GUC:** `set_current_tenant(session, tid)` →
  `SELECT set_config('app.current_tenant', :tid, true)` — bind param (injection-safe),
  `is_local=true` → **transaction-local**.

> ⚠️ **Transaction trap:** with `is_local=true` the GUC is cleared on commit. Write
> endpoints **re-pin** the tenant for **post-commit reads** (`bots.py` create/update/
> config-update). Use `selectinload(Bot.config)` to avoid an async lazy-load.
>
> ⚠️ **Own-session components:** the ingestion pipeline (M3) and the chat
> orchestrator (M5) open their **own** `session_factory()` blocks and **re-pin** the
> tenant in each — the request session may be gone mid-stream and the GUC is
> transaction-local. In tests these globals are rebound to a NullPool sessionmaker
> (see §9).

---

## 6. Data model

```
Tenant (RLS-exempt)
 ├── AdminUser (RLS-exempt)         email unique, password argon2, role=owner
 └── Bot                            name, status(active|disabled), allowed_domains[]
      ├── BotConfig (1-1)           welcome_message, system_prompt, model,
      │                             temperature, suggested_questions[], primary_color
      ├── Document                  file_*, status(uploaded|processing|ready|failed),
      │    └── Chunk                storage_path, chunk_count, deleted_at (soft)
      │         chunk_index, content, content_tokens,
      │         embedding vector(1536) [HNSW cosine], bot_id denormalized
      ├── Conversation              session_id, is_preview, status(active|closed)
      │    └── Message              role(user|assistant|system), content,
      │                            sources[] (citations), status(streaming|completed|aborted)
      └── UsageEvent                event_type(chat|embedding|document_upload),
                                    tokens_in/out, embedding_tokens, cost_usd
```

**Every tenant-scoped table has `tenant_id`.** `Chunk.bot_id` and `Chunk.tenant_id`
are denormalized (to avoid a join on the retrieval hot path). Embedding dimension is
**1536** (`text-embedding-3-small`). ANN index: **HNSW + vector_cosine_ops** (`<=>`).

---

## 7. API surface (current)

All admin endpoints require `Authorization: Bearer <admin JWT>`.

### Auth (M1) — `/api/auth`

| Method | Path | Description | Success |
|---|---|---|---|
| POST | `/register` | Public self-service: tenant + owner admin + auto-login | 201 `TokenResponse` |
| POST | `/login` | email+password → admin JWT (generic 401) | 200 `TokenResponse` |
| GET | `/me` | Current admin + tenant | 200 `MeResponse` |

### Bots (M2) — `/api/bots`

| Method | Path | Description | Success |
|---|---|---|---|
| POST | `` | Bot + default BotConfig (1-1) | 201 `BotOut` |
| GET | `` | Tenant's bots (created desc) | 200 `BotOut[]` |
| GET | `/{bot_id}` | Single bot (+config) | 200 `BotOut` |
| PATCH | `/{bot_id}` | name/status/allowed_domains | 200 `BotOut` |
| DELETE | `/{bot_id}` | Delete (config cascade) | 204 |
| GET | `/{bot_id}/config` | Read config | 200 `BotConfigOut` |
| PATCH | `/{bot_id}/config` | Update config | 200 `BotConfigOut` |

### Documents (M3) — `/api/bots/{bot_id}/documents`

| Method | Path | Description | Success |
|---|---|---|---|
| POST | `` | Multipart upload → parse/chunk/embed/store pipeline | 201 `DocumentOut` |
| GET | `` | Tenant/bot documents | 200 `DocumentOut[]` |
| GET | `/{document_id}` | Single document | 200 `DocumentOut` |
| DELETE | `/{document_id}` | Soft delete (`deleted_at`) | 204 |

Guards: 415 unsupported extension, 413 > 10 MB, 422 empty. The pipeline writes
`UsageEvent` (`document_upload` + `embedding`) and re-pins the tenant per session.

### Widget (M4) — `/api/widget`

| Method | Path | Auth | Description | Success |
|---|---|---|---|---|
| POST | `/session` | **public** | Embed sends `bot_id`+`tenant_id`; RLS self-validates the pair; Origin whitelist; mints widget token | 201 `WidgetSessionResponse` |
| GET | `/config` | widget/preview | Re-fetch safe config (on remount) | 200 `WidgetConfigOut` |
| POST | `/{bot_id}/preview-session` *(on `/api/bots`)* | admin | Mints a 5-min preview token (no Origin check) | 201 `WidgetSessionResponse` |

**Bootstrap = "Option D":** the public session endpoint can't know the tenant, yet
RLS is FORCE'd. The embed carries **both** `bot_id` and `tenant_id` (both public,
unguessable UUIDs). The endpoint pins RLS to the *claimed* tenant, then
`SELECT bot WHERE id=bot_id` — a wrong tenant claim finds **no row** → 404. No new
policy/role/migration; nothing leaks. `WidgetConfigOut` never carries
`system_prompt`/`model`/`temperature`.

### Chat (M5) — `/api/widget/chat` (SSE)

| Method | Path | Auth | Description | Success |
|---|---|---|---|---|
| POST | `/chat` | widget/preview | Streams the reply as **Server-Sent Events** | 200 `text/event-stream` |

Body: `{ message, conversation_id? }`. A bad `conversation_id` (not owned by the
session) → **404** before the stream starts. Event order:
`meta` (conversation_id, message_id) → `sources` (citations) → many `delta` (text)
→ `done` (token counts) | `error`. Retrieval is cosine top-k (k=4, `max_distance=0.4`);
if nothing is close enough it returns `[]` and the system prompt tells the model to
admit ignorance. Tokens counted via tiktoken; a `chat` `UsageEvent` is written
**except** on preview turns. Moderation is a no-op seam (`_moderate`, real provider
in M8).

### Health (M0) — `/api/health`

`/api/health` (status+version) · `/api/health/live` · `/api/health/ready` (DB down → 503).

**API contract rules:**

- `tenant_id` is **never taken from the body** — it comes from the authenticated
  admin + RLS.
- Cross-tenant access → **404** (not 403; so the id's existence isn't confirmed).
- PATCH = `exclude_unset` (only provided fields change).
- DTOs are separate from ORM (`schemas.py`) — internal columns like `password_hash`
  never leak.

---

## 8. Config fields (`chatbot/config.py`)

`service_name, environment, cors_origins`, `database_url` (SecretStr),
`db_pool_size=5`, `db_max_overflow=2`, `openai_api_key` (SecretStr),
`openai_embedding_model`, `openai_embedding_dim=1536`, `openai_chat_model`,
`storage_backend`, `storage_local_path`, `jwt_secret` (SecretStr),
`jwt_algorithm=HS256`, `admin_token_ttl=3600`, `widget_token_ttl=86400`,
`preview_token_ttl=300`.

---

## 9. Conventions (specific to this project)

- **Python:** all imports at the top of the file; module-level constants UPPER_CASE
  (`TEST_SESSION`, `EMBEDDING_DIM`); on `.get_secret_value()` calls use the double
  suppression `# type: ignore[attr-defined]  # pylint: disable=no-member`.
- **Migration:** `# pylint: disable=no-member,invalid-name` header.
- **pytest fixture shadowing:** on fixture-injected params use
  `# pylint: disable=redefined-outer-name` (symbol is `redefined`, not `redefining`).
- **Tests hit the live Neon dev DB:** ASGITransport does not start the lifespan, but
  the engine is import-time; to avoid loop conflicts the conftest uses a **NullPool
  test engine + `get_session` dependency override**. Cleanup: delete tenants whose
  admin email has the `m1test_` prefix (FK cascade).
- **Own-session globals in tests:** `pipeline.session_factory` (M3) and
  `chat.session_factory` (M5) are rebound to the NullPool `TEST_SESSION` in conftest,
  else per-test event loops raise "Event loop is closed".
- **Deterministic message order:** the user + assistant messages of one turn are
  inserted in the same transaction, so Postgres `now()` (transaction time) would tie
  them; `chat.py` sets explicit `created_at` (`now`, `now+1ms`) so history replay and
  display order stay deterministic.
- **SSE:** hand-rolled (`event: … / data: …\n\n`, `X-Accel-Buffering: no`), no
  `sse-starlette` dependency; `StreamingResponse` with `media_type="text/event-stream"`.
- **204 routes:** must be body-less in FastAPI → `response_class=Response`.
