# Level-3 Chatbot — Mimari ve Kararlar (Living Doc)

> **Amaç:** Bu dosya projenin tek doğruluk kaynağı (single source of truth).
> Her milestone sonunda güncellenir. Kod ile bu doküman çelişirse **kod
> kazanır** ama çelişki bir düzeltme sinyalidir.
> Son güncelleme: **M2 sonu** (bot + bot-config CRUD).

---

## 1. Ürün konumlandırma (kritik reframe)

| | Level-1 / Level-2 | **Level-3 (bu proje)** |
|---|---|---|
| Model | B2C, tek kullanıcı (Gateway arkasında) | **B2B2C, multi-tenant SaaS** |
| Müşteri | Birey | **Şirket (tenant)** |
| Son kullanıcı | Kaydolan kişi | Tenant'ın sitesindeki **anonim ziyaretçi** |

**Sonuç:** Level-1/2 kitlesi (birey) ≠ Level-3 kitlesi (şirket) → "tek kimlik /
single identity" değeri sanıldığından düşük. Level-3 kendi kontrol düzlemini
backend'de taşıyor.

---

## 2. Kilitlenen forklar (onaylı)

- **FORK A = A1** — Tam bağımsız. Gateway'e **dokunulmuyor**. İleride Level-3'ün
  önüne **ayrı bir B2B CDN/gateway** eklenebilir (ürün-önü katman, iş mantığı
  taşımaz). Neden: Level-3 B2B; Gateway'in B2C kontrol-düzlemi burada backend'e
  taşındığı için Gateway MVP'de sadece dumb-passthrough olurdu (gereksiz hop).
- **FORK B = B2** — Level-3 **kendi RAG'ını** taşıyor; RAG-Service'in kanıtlanmış
  yapısını (chunker/embedder/retriever/pgvector) **tenant/bot scope'una uyarlayarak
  genişletiyor** + **Embedder/Retriever Protocol seam**. Prod RAG-Service'e
  dokunulmuyor (Level-2 ona bağlı).
- **Genel:** Thin-slice MVP = self-contained vertical (A1 + B2), seam'ler ileride
  konsolidasyon için hazır.

---

## 3. Teknoloji yığını (lock-in)

**Backend:** FastAPI + **plain SQLAlchemy 2.0 async** (plan'daki SQLModel yerine —
RAG-Service ile kod copy-adapt tutarlılığı için) + asyncpg + Alembic + PyJWT +
argon2-cffi + slowapi + pgvector.
**DB:** Neon PostgreSQL (EU), `ai-platform` projesi / `production` branch içinde
**ayrı database `ai_chatbotdb`** + **ayrı owner rolü `ai_chatbot_owner`**
(credential izolasyonu). Direct connection (pooler KAPALI).
**OpenAI:** proje-scoped restricted key (`Model capabilities = Request`).
**Widget (M6):** Lit + Shadow DOM. **Admin panel (M7):** Angular.
**Test:** pytest + pytest-asyncio + httpx ASGITransport (+ Playwright ileride).
**Dev port:** `8200` (RAG=8100, Level-2 BE=8001, Level-1 BE=8000).

---

## 4. İki auth düzlemi (auth planes)

Tek `JWT_SECRET`, **HS256**. `scope` claim ile ayrışır.

| Scope | Kim | TTL | Milestone |
|---|---|---|---|
| `admin` | Tenant yöneticisi (panel) | 3600s (1h) | **M1 ✅** |
| `widget` | Anonim ziyaretçi (embed) | 86400s (24h) | M4 |
| `preview` | Admin canlı önizleme | 300s (5m) | M4 |

**Token claim'leri:** `sub`, `scope`, `iat`, `exp` + admin için `tenant_id`, `role`.

`get_current_admin` (deps.py) = **tek seam**: token decode (scope=admin) →
**RLS tenant GUC pin** → canlı `AdminUser` yükle (id+tenant_id+is_active). Her
tenant-scoped handler buna bağlı → hiçbir handler başka tenant'ın verisine erişemez.

---

## 5. Row-Level Security (RLS) — izolasyonun kalbi

- **7 tenant-scoped tablo** RLS ENABLE + **FORCE** (tek-rol Neon DB'de FORCE şart,
  yoksa owner RLS'i bypass eder): `bots, bot_configs, documents, chunks,
  conversations, messages, usage_events`.
- **RLS dışı:** `tenants`, `admin_users` (login/administration cross-tenant
  kontrol-düzlemi işlemleri).
- **Policy `tenant_isolation`** (her tabloda, hem USING hem WITH CHECK):
  `tenant_id = current_setting('app.current_tenant', true)::uuid`
  → GUC set değilse `current_setting` NULL döner → hiçbir satır görünmez/yazılamaz.
- **GUC set:** `set_current_tenant(session, tid)` →
  `SELECT set_config('app.current_tenant', :tid, true)` — bind param (injection-safe),
  `is_local=true` → **transaction-local**.

> ⚠️ **Transaction tuzağı:** `is_local=true` GUC commit'te sıfırlanır. Yazma
> endpoint'leri **commit sonrası okuma** için tenant'ı **yeniden pin'ler**
> (`bots.py` create/update/config-update). Async lazy-load'dan kaçınmak için
> `selectinload(Bot.config)`.

---

## 6. Veri modeli

```
Tenant (RLS dışı)
 ├── AdminUser (RLS dışı)            email unique, password argon2, role=owner
 └── Bot                            name, status(active|disabled), allowed_domains[]
      ├── BotConfig (1-1)           welcome_message, system_prompt, model,
      │                             temperature, suggested_questions[], primary_color
      ├── Document                  file_*, status(uploaded|processing|ready|failed),
      │    └── Chunk                storage_path, chunk_count, deleted_at (soft)
      │         chunk_index, content, content_tokens,
      │         embedding vector(1536) [HNSW cosine], bot_id denormalize
      ├── Conversation              session_id, is_preview, status(active|closed)
      │    └── Message              role(user|assistant|system), content,
      │                            sources[] (citations), status(streaming|completed|aborted)
      └── UsageEvent                event_type(chat|embedding|document_upload),
                                    tokens_in/out, embedding_tokens, cost_usd
```

**Her tenant-scoped tabloda `tenant_id` var.** `Chunk.bot_id` ve `Chunk.tenant_id`
denormalize (retrieval hot-path'te join'den kaçınmak için). Embedding boyutu
**1536** (`text-embedding-3-small`). ANN index: **HNSW + vector_cosine_ops** (`<=>`).

---

## 7. API yüzeyi (mevcut)

Tüm admin endpoint'leri `Authorization: Bearer <admin JWT>` ister.

### Auth (M1) — `/api/auth`

| Metot | Yol | Açıklama | Başarı |
|---|---|---|---|
| POST | `/register` | Public self-service: tenant + owner admin + auto-login | 201 `TokenResponse` |
| POST | `/login` | email+password → admin JWT (generic 401) | 200 `TokenResponse` |
| GET | `/me` | Mevcut admin + tenant | 200 `MeResponse` |

### Bots (M2) — `/api/bots`

| Metot | Yol | Açıklama | Başarı |
|---|---|---|---|
| POST | `` | Bot + default BotConfig (1-1) | 201 `BotOut` |
| GET | `` | Tenant'ın botları (created desc) | 200 `BotOut[]` |
| GET | `/{bot_id}` | Tek bot (+config) | 200 `BotOut` |
| PATCH | `/{bot_id}` | name/status/allowed_domains | 200 `BotOut` |
| DELETE | `/{bot_id}` | Sil (config cascade) | 204 |
| GET | `/{bot_id}/config` | Config oku | 200 `BotConfigOut` |
| PATCH | `/{bot_id}/config` | Config güncelle | 200 `BotConfigOut` |

### Health (M0) — `/api/health`

`/api/health` (durum+versiyon) · `/api/health/live` · `/api/health/ready` (DB down → 503).

**API sözleşme kuralları:**

- `tenant_id` **asla body'den alınmaz** — auth'lu admin'den + RLS.
- Cross-tenant erişim → **404** (403 değil; id'nin varlığını doğrulamamak için).
- PATCH = `exclude_unset` (sadece gönderilen alanlar değişir).
- DTO'lar ORM'den ayrı (`schemas.py`) — `password_hash` gibi iç kolonlar asla sızmaz.

---

## 8. Config alanları (`chatbot/config.py`)

`service_name, environment, cors_origins`, `database_url` (SecretStr),
`db_pool_size=5`, `db_max_overflow=2`, `openai_api_key` (SecretStr),
`openai_embedding_model`, `openai_embedding_dim=1536`, `openai_chat_model`,
`storage_backend`, `storage_local_path`, `jwt_secret` (SecretStr),
`jwt_algorithm=HS256`, `admin_token_ttl=3600`, `widget_token_ttl=86400`,
`preview_token_ttl=300`.

---

## 9. Konvansiyonlar (bu projeye özel)

- **Python:** tüm import'lar dosya başında; module-level constant UPPER_CASE
  (`TEST_SESSION`, `EMBEDDING_DIM`); `.get_secret_value()` çağrılarında ikili
  suppression `# type: ignore[attr-defined]  # pylint: disable=no-member`.
- **Migration:** `# pylint: disable=no-member,invalid-name` header.
- **pytest fixture shadowing:** fixture inject edilen param'da
  `# pylint: disable=redefined-outer-name` (symbol `redefined`, `redefining` değil).
- **Testler canlı Neon dev DB'ye vurur:** ASGITransport lifespan başlatmaz ama
  engine import-time; loop çakışmasını önlemek için conftest'te **NullPool test
  engine + `get_session` dependency override**. Cleanup: `m1test_` prefix'li email →
  tenant sil (FK cascade).
- **204 route:** FastAPI'de gövdesiz olmalı → `response_class=Response`.
