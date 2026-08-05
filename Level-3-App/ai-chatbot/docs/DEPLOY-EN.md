# Deployment Guide (EN) — Level-3 Chatbot SaaS

> **PREPARE-ONLY.** This document and the accompanying artifacts (Dockerfile,
> `railway.json`, `_redirects`) make the app deploy-ready. **No real deploy is
> performed here** — you run the steps below with your own accounts, domains,
> and secrets. All domains here are placeholders.

---

## 1. What gets deployed

The system is **three independently deployable units** plus one managed database:

| Unit | Tech | Target | Placeholder domain | Local port |
|------|------|--------|--------------------|-----------|
| Backend API | FastAPI + uvicorn | Railway (Docker) | `api.example.com` | 8200 |
| Admin panel | Angular SPA | Cloudflare Pages | `admin.example.com` | 4202 |
| Widget bundle | Vite IIFE (`widget.js`) | Cloudflare Pages / CDN | `cdn.example.com` | 5173 |
| Database | PostgreSQL + pgvector | **Neon** (managed, external) | — | — |

**GDPR / EU residency:** pick EU regions everywhere — Railway **Amsterdam**,
Neon **Frankfurt**, Cloudflare (EU data localization). OpenAI is the only
non-EU processor; document it in your Record of Processing Activities.

```
                 ┌─────────────────────────┐
  Tenant site ──▶│ widget.js (Cloudflare)   │──┐
                 └─────────────────────────┘  │  HTTPS + CORS
                 ┌─────────────────────────┐  ▼
  Admin user  ──▶│ admin SPA (Cloudflare)   │──▶ Backend API (Railway) ──▶ Neon (Frankfurt)
                 └─────────────────────────┘        │
                                                     └──▶ OpenAI (embeddings, chat, moderation)
```

---

## 2. Backend → Railway (Docker)

Artifacts already in `backend/`: `Dockerfile`, `.dockerignore`, `railway.json`.

### 2.1 Backend environment variables (set in Railway, NOT in a committed file)

| Var | Prod value | Notes |
|-----|-----------|-------|
| `ENVIRONMENT` | `production` | |
| `DATABASE_URL` | Neon prod connection string | `postgresql://…?sslmode=require` |
| `OPENAI_API_KEY` | your key | |
| `JWT_SECRET` | 32+ random bytes | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `CORS_ORIGINS` | `https://admin.example.com,https://<tenant-site>` | admin + every embedding origin |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | must match the dim used to embed existing chunks |
| `OPENAI_EMBEDDING_DIM` | `1536` | changing it means re-embedding everything |
| `OPENAI_CHAT_MODEL` | `gpt-4o-mini` | |
| `STORAGE_BACKEND` | `local` | ⚠️ see 2.3 |
| `STORAGE_LOCAL_PATH` | `/app/storage` | mount a volume here |
| `RATE_LIMIT_*` | defaults | ⚠️ see 2.4 |
| `MODERATION_ENABLED` | `true` | |
| `PORT` | injected by Railway | Dockerfile binds `$PORT` |

Never commit real secret values. `.env` is git-ignored; `.env.example` is the
template only.

### 2.2 Deploy steps (you run these)

```bash
# From backend/ — install the CLI once, then link and deploy.
npm i -g @railway/cli
railway login
railway init            # create/select a Railway project (choose EU / Amsterdam)
railway up              # builds the Dockerfile and deploys
```

Railway reads `railway.json`: Docker build, healthcheck on `/api/health/ready`,
restart-on-failure, single replica. Set the env vars from 2.1 in the Railway
dashboard (Variables) before the first successful boot.

### 2.3 ⚠️ Uploaded-file storage is ephemeral

Railway container filesystems are **wiped on every redeploy**. With
`STORAGE_BACKEND=local`, tenant-uploaded documents would disappear.

- **MVP fix:** attach a Railway **persistent volume** mounted at `/app/storage`
  and set `STORAGE_LOCAL_PATH=/app/storage`.
- **Proper fix (future):** switch `STORAGE_BACKEND` to an S3-compatible EU
  object store (Cloudflare R2, Hetzner Object Storage). `storage.py` is already
  a swappable seam — no caller changes needed.

### 2.4 ⚠️ Rate limiting with more than one instance

Rate-limit counters are **in-memory per instance**. If you scale to
`numReplicas > 1`, the effective limit becomes `configured × replicas` (limit
leaks). Before scaling out, point slowapi at Redis (Upstash EU or self-hosted)
via `Limiter(storage_uri="redis://…")`. See `chatbot/ratelimit.py`.

---

## 3. Admin panel → Cloudflare Pages (Angular SPA)

Artifact: `admin/public/_redirects` (SPA fallback so deep links / refresh work).

### Cloudflare Pages project settings

| Setting | Value |
|---------|-------|
| Framework preset | Angular (or None) |
| Build command | `npm ci && npm run build -- --configuration production` |
| Build output directory | `dist/admin/browser` |
| Node version | 20 (or the repo's `.nvmrc`) |

**Runtime config:** the admin needs the backend base URL
(`https://api.example.com`). If the app reads it from an Angular environment
file, set `src/environments/environment.prod.ts` before build; if from a
runtime `config.json`, publish it alongside the build. (Wire this in the
component/service layer — not covered by this prepare step.)

Deploy: connect the repo in the Cloudflare Pages dashboard, or
`npx wrangler pages deploy dist/admin/browser`.

---

## 4. Widget → Cloudflare Pages / CDN (static bundle)

The widget builds to a single self-mounting `dist/widget.js` (IIFE). Customers
embed it with a `<script>` tag.

| Setting | Value |
|---------|-------|
| Build command | `npm ci && npm run build` |
| Build output directory | `dist` |

Serve `widget.js` from a stable URL (`https://cdn.example.com/widget.js`).
Cloudflare Pages serves it with permissive access by default; ensure the
backend's `CORS_ORIGINS` includes each tenant site origin that will call the
widget session/chat endpoints.

Embed snippet a tenant pastes:

```html
<script
  src="https://cdn.example.com/widget.js"
  data-bot-id="<TENANT_BOT_ID>"
  data-api-base="https://api.example.com"
  defer></script>
```

---

## 5. Database → Neon (managed, external)

- Create a Neon project in **Frankfurt** (separate from any other app's DB).
- Enable the `vector` extension (pgvector) — required by the chunk embeddings.
- Migrations are **not** run automatically on deploy. Promotion strategy and
  the exact commands are in **[DEPLOY-DB-MIGRATION-EN.md](DEPLOY-DB-MIGRATION-EN.md)**
  (Slice E). **Do not** point `alembic upgrade head` at production without
  reading it.

### ⚠️ Security follow-up (tracked separately, not part of M8)

The current Neon app role bypasses Row-Level Security, so tenant isolation
relies solely on app-level `WHERE tenant_id` filters. Before production,
create a dedicated non-owner `NOBYPASSRLS` runtime role for `DATABASE_URL` and
keep the owner role for migrations only. This is a known follow-up.

---

## 6. Go-live checklist

- [ ] Neon prod DB created (Frankfurt), `vector` extension enabled
- [ ] Migrations applied per DEPLOY-DB-MIGRATION (dedicated role recommended)
- [ ] Backend env vars set in Railway (EU/Amsterdam); `JWT_SECRET` freshly generated
- [ ] Persistent volume mounted at `/app/storage` (or object storage configured)
- [ ] `CORS_ORIGINS` lists admin domain + every tenant embedding origin
- [ ] Admin built & deployed (Cloudflare Pages), backend base URL wired
- [ ] Widget built & deployed to CDN; embed snippet verified on a test page
- [ ] Health checks green: `/api/health/live`, `/api/health/ready`
- [ ] Redis planned before scaling backend past one replica
