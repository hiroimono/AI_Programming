# Deployment Rehberi (TR) — Level-3 Chatbot SaaS

> **SADECE HAZIRLIK.** Bu doküman ve beraberindeki artefaktlar (Dockerfile,
> `railway.json`, `_redirects`) uygulamayı deploy'a hazır hale getirir.
> **Burada gerçek deploy YAPILMAZ** — aşağıdaki adımları kendi hesabın,
> domainlerin ve secret'larınla sen çalıştırırsın. Buradaki tüm domainler
> placeholder'dır.

---

## 1. Neler deploy ediliyor

Sistem, biri managed veritabanı olmak üzere **üç bağımsız deploy edilebilir
birimden** oluşur:

| Birim | Teknoloji | Hedef | Placeholder domain | Lokal port |
|-------|-----------|-------|--------------------|-----------|
| Backend API | FastAPI + uvicorn | Railway (Docker) | `api.example.com` | 8200 |
| Admin paneli | Angular SPA | Cloudflare Pages | `admin.example.com` | 4202 |
| Widget bundle | Vite IIFE (`widget.js`) | Cloudflare Pages / CDN | `cdn.example.com` | 5173 |
| Veritabanı | PostgreSQL + pgvector | **Neon** (managed, harici) | — | — |

**GDPR / EU yerleşimi:** her yerde EU region seç — Railway **Amsterdam**,
Neon **Frankfurt**, Cloudflare (EU data localization). OpenAI tek AB-dışı
işleyendir; Veri İşleme Envanteri'ne (Record of Processing Activities) yaz.

```
                 ┌─────────────────────────┐
  Tenant sitesi ▶│ widget.js (Cloudflare)   │──┐
                 └─────────────────────────┘  │  HTTPS + CORS
                 ┌─────────────────────────┐  ▼
  Admin kullanıcı▶│ admin SPA (Cloudflare)  │──▶ Backend API (Railway) ──▶ Neon (Frankfurt)
                 └─────────────────────────┘        │
                                                     └──▶ OpenAI (embedding, chat, moderation)
```

---

## 2. Backend → Railway (Docker)

`backend/` içinde hazır artefaktlar: `Dockerfile`, `.dockerignore`, `railway.json`.

### 2.1 Backend environment değişkenleri (Railway'de tanımlanır, commit'lenmez)

| Değişken | Prod değeri | Not |
|----------|-------------|-----|
| `ENVIRONMENT` | `production` | |
| `DATABASE_URL` | Neon prod connection string | `postgresql://…?sslmode=require` |
| `OPENAI_API_KEY` | senin anahtarın | |
| `JWT_SECRET` | 32+ rastgele byte | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `CORS_ORIGINS` | `https://admin.example.com,https://<tenant-site>` | admin + her gömülü origin |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | mevcut chunk'ların dim'iyle eşleşmeli |
| `OPENAI_EMBEDDING_DIM` | `1536` | değişirse her şeyi yeniden embed etmen gerekir |
| `OPENAI_CHAT_MODEL` | `gpt-4o-mini` | |
| `STORAGE_BACKEND` | `local` | ⚠️ 2.3'e bak |
| `STORAGE_LOCAL_PATH` | `/app/storage` | buraya volume mount et |
| `RATE_LIMIT_*` | default'lar | ⚠️ 2.4'e bak |
| `MODERATION_ENABLED` | `true` | |
| `PORT` | Railway enjekte eder | Dockerfile `$PORT`'a bind eder |

Gerçek secret değerlerini ASLA commit'leme. `.env` git-ignore'lu;
`.env.example` sadece şablon.

### 2.2 Deploy adımları (sen çalıştırırsın)

```bash
# backend/ içinden — CLI'ı bir kez kur, sonra link'le ve deploy et.
npm i -g @railway/cli
railway login
railway init            # Railway projesi oluştur/seç (EU / Amsterdam seç)
railway up              # Dockerfile'ı build eder ve deploy eder
```

Railway `railway.json`'u okur: Docker build, `/api/health/ready` healthcheck,
hata halinde restart, tek replica. İlk başarılı boot'tan ÖNCE 2.1'deki env
değişkenlerini Railway dashboard'da (Variables) tanımla.

### 2.3 ⚠️ Yüklenen dosya deposu geçici (ephemeral)

Railway container dosya sistemi **her redeploy'da silinir**.
`STORAGE_BACKEND=local` ile tenant'ların yüklediği dokümanlar kaybolur.

- **MVP çözümü:** Railway **kalıcı volume** oluştur, `/app/storage`'a mount et,
  `STORAGE_LOCAL_PATH=/app/storage` ayarla.
- **Doğru çözüm (gelecek):** `STORAGE_BACKEND`'i S3-uyumlu EU object store'a
  (Cloudflare R2, Hetzner Object Storage) geçir. `storage.py` zaten swappable
  bir seam — çağıran kodda değişiklik gerekmez.

### 2.4 ⚠️ Birden fazla instance ile rate limiting

Rate-limit sayaçları **instance başına in-memory**. `numReplicas > 1` yaparsan
efektif limit `ayar × replica` olur (limit sızar). Yatay ölçeklemeden ÖNCE
slowapi'yi Redis'e (Upstash EU veya self-hosted) yönlendir:
`Limiter(storage_uri="redis://…")`. Bkz. `chatbot/ratelimit.py`.

---

## 3. Admin paneli → Cloudflare Pages (Angular SPA)

Artefakt: `admin/public/_redirects` (deep link / refresh çalışsın diye SPA
fallback).

### Cloudflare Pages proje ayarları

| Ayar | Değer |
|------|-------|
| Framework preset | Angular (veya None) |
| Build command | `npm ci && npm run build -- --configuration production` |
| Build output directory | `dist/admin/browser` |
| Node sürümü | 20 (veya repo'nun `.nvmrc`'i) |

**Runtime config:** admin backend base URL'ine ihtiyaç duyar
(`https://api.example.com`). Angular environment dosyasından okuyorsa build'den
önce `src/environments/environment.prod.ts`'i ayarla; runtime `config.json`'dan
okuyorsa build yanına yayınla. (Bunu component/service katmanında bağla — bu
hazırlık adımının kapsamında değil.)

Deploy: Cloudflare Pages dashboard'da repo'yu bağla veya
`npx wrangler pages deploy dist/admin/browser`.

---

## 4. Widget → Cloudflare Pages / CDN (statik bundle)

Widget tek, kendini mount eden `dist/widget.js` (IIFE) olarak build olur.
Müşteriler `<script>` etiketiyle gömer.

| Ayar | Değer |
|------|-------|
| Build command | `npm ci && npm run build` |
| Build output directory | `dist` |

`widget.js`'i sabit bir URL'den (`https://cdn.example.com/widget.js`) servis et.
Cloudflare Pages varsayılan olarak erişime açık servis eder; backend'in
`CORS_ORIGINS`'inin widget session/chat endpoint'lerini çağıracak her tenant
site origin'ini içerdiğinden emin ol.

Tenant'ın yapıştırdığı gömme snippet'i:

```html
<script
  src="https://cdn.example.com/widget.js"
  data-bot-id="<TENANT_BOT_ID>"
  data-api-base="https://api.example.com"
  defer></script>
```

---

## 5. Veritabanı → Neon (managed, harici)

- **Frankfurt**'ta Neon projesi oluştur (diğer app'lerin DB'sinden ayrı).
- `vector` extension'ı (pgvector) etkinleştir — chunk embedding'leri için şart.
- Migration'lar deploy'da **otomatik çalışmaz**. Promotion stratejisi ve kesin
  komutlar **[DEPLOY-DB-MIGRATION-TR.md](DEPLOY-DB-MIGRATION-TR.md)** içinde
  (Slice E). Onu okumadan `alembic upgrade head`'i production'a **yöneltme**.

### ⚠️ Güvenlik takibi (ayrı izleniyor, M8 kapsamı değil)

Mevcut Neon app rolü Row-Level Security'yi bypass ediyor; tenant izolasyonu şu
an yalnızca app-level `WHERE tenant_id` filtrelerine bağlı. Production'dan önce
`DATABASE_URL` için ayrı bir non-owner `NOBYPASSRLS` runtime rolü oluştur, owner
rolü sadece migration'da kullan. Bu bilinen bir takip işi.

---

## 6. Yayına-alma kontrol listesi

- [ ] Neon prod DB oluşturuldu (Frankfurt), `vector` extension aktif
- [ ] Migration'lar DEPLOY-DB-MIGRATION'a göre uygulandı (ayrı rol önerilir)
- [ ] Backend env değişkenleri Railway'de tanımlı (EU/Amsterdam); `JWT_SECRET` yeni üretildi
- [ ] `/app/storage`'a kalıcı volume mount edildi (veya object storage yapılandırıldı)
- [ ] `CORS_ORIGINS` admin domain + her tenant gömme origin'ini listeliyor
- [ ] Admin build & deploy edildi (Cloudflare Pages), backend base URL bağlandı
- [ ] Widget build & CDN'e deploy edildi; gömme snippet'i test sayfasında doğrulandı
- [ ] Health check'ler yeşil: `/api/health/live`, `/api/health/ready`
- [ ] Backend tek replica'yı aşmadan önce Redis planlandı
