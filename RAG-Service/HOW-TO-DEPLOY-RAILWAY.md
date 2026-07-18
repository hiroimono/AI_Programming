# Deploying RAG-Service to Railway

> **Audience:** you, the operator, clicking in the Railway dashboard.
> **Goal:** get RAG-Service running in production so that document
> upload on the AI Writing Assistant stops returning **503**.
>
> This is a runbook: follow it top to bottom once. Every prod-affecting
> config is either in this repo (`Dockerfile`, `railway.toml`) or listed
> as an explicit environment variable below.

---

## 1. Why this service must exist

The writer backend (`Level-2-App`) does **not** store or index documents
itself. When the browser uploads a file, the chain is:

```
Browser (ai-writing-assistant.pages.dev)
    │  POST /apps/writer/api/documents  + Gateway JWT
    ▼
Gateway (Railway, YARP)  ── strips /apps/writer ──►
    │  POST /api/documents
    ▼
Writer backend (Railway)
    │  POST /api/documents  + short-lived internal JWT
    ▼
RAG-Service (Railway)  ◄── THIS is what we are deploying
    │
    ├─► Neon Postgres  (documents, chunks, pgvector embeddings)
    └─► OpenAI          (text-embedding-3-small)
```

If RAG-Service is missing, the writer backend's call to it fails
(connection refused / timeout) and the whole request surfaces as a
**503** in the browser. That is the exact bug this deploy fixes.

---

## 2. Prerequisites

- [ ] Railway project already hosting Gateway + writer backend.
- [ ] Neon Postgres reachable (the same `gatewaydb` the Gateway uses is
      fine — see §5).
- [ ] OpenAI API key (same one the writer backend uses is fine).
- [ ] A generated internal JWT secret (see §4). Generate with:
      `powershell
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  `
- [ ] This repo pushed to GitHub (Railway deploys from the repo).

---

## 3. Create the Railway service

1. Open the Railway **project** that already contains Gateway + writer.
2. **New** → **GitHub Repo** → pick `hiroimono/AI_Programming`.
3. In the new service's **Settings**:
   - **Root Directory:** `RAG-Service`
     (so Railway builds from the folder that has the `Dockerfile`).
   - **Build:** Railway auto-detects `railway.toml` → builder =
     `DOCKERFILE`. No manual build command needed.
   - **Watch Paths** (Settings → Deploy): set to `RAG-Service/**` so a
     change to Level-1/Level-2 code does not trigger a rag-service
     rebuild.
4. Do **not** deploy yet — set the variables first (§4), otherwise the
   first boot crashes on a missing `DATABASE_URL`.

> **.NET 8 → nothing here**; this is Python. Just noting the Root
> Directory + Watch Paths pattern is the same one you already use for
> the writer service.

---

## 4. Environment variables (the critical part)

Set these in the rag-service **Variables** panel. Names must match
exactly — the app reads them verbatim.

| Variable                 | Value                                                                                         | Notes                                                                        |
| ------------------------ | --------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| `DATABASE_URL`           | `postgresql://rag_service_user:PWD@HOST.eu-central-1.aws.neon.tech/gatewaydb?sslmode=require` | Same Neon DB as dev/Gateway. Code rewrites it to asyncpg + strips `sslmode`. |
| `OPENAI_API_KEY`         | `sk-...`                                                                                      | Required for embeddings. Reuse the writer's key.                             |
| `INTERNAL_JWT_SECRET`    | _(the 32-byte secret from §4 below)_                                                          | **Must byte-match** the writer's `RAG_INTERNAL_JWT_SECRET`.                  |
| `INTERNAL_JWT_ALGORITHM` | `HS256`                                                                                       | Default; set explicitly for clarity.                                         |
| `ENVIRONMENT`            | `production`                                                                                  | Toggles logging defaults.                                                    |
| `STORAGE_BACKEND`        | `local`                                                                                       | MVP. R2/Hetzner later.                                                       |
| `STORAGE_LOCAL_PATH`     | `/app/storage`                                                                                | Matches the Dockerfile volume mount point (§6).                              |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small`                                                                      | Optional (has a default).                                                    |
| `OPENAI_EMBEDDING_DIM`   | `1536`                                                                                        | Optional (has a default).                                                    |
| `DB_POOL_SIZE`           | `5`                                                                                           | Optional. Neon free tier is connection-tight.                                |
| `DB_MAX_OVERFLOW`        | `2`                                                                                           | Optional.                                                                    |
| `CORS_ORIGINS`           | _(leave empty)_                                                                               | rag-service is never called from a browser.                                  |

> `PORT` is injected by Railway automatically — **do not set it**. The
> Dockerfile's start command reads `$PORT`.

### The shared internal secret

The writer mints an HS256 token; rag-service verifies it with the same
secret. If they differ by a single byte, every RAG call is **401**.

1. Generate ONE secret (already done, or regenerate):

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. Set it here as `INTERNAL_JWT_SECRET`.
3. Set the **same value** on the **writer** service as
   `RAG_INTERNAL_JWT_SECRET` (see §8).

---

## 5. Database: reuse `gatewaydb` or use a fresh one?

**Recommended: reuse the same Neon `gatewaydb`** that dev and Gateway
already use. The RAG tables live in isolated schemas
(`rag_shared`, `rag_level2_writer`, `rag_level3_chatbot`) and never touch
Gateway's `public` schema.

- **Reusing `gatewaydb` (schemas already exist):** the least-privilege
  `rag_service_user` works as-is. On boot, `alembic upgrade head` sees
  the schemas exist, skips schema creation, and (being already at head)
  is a no-op. Nothing to do. ✅
- **Fresh Neon DB (schemas do NOT exist yet):** the connecting role must
  be able to create the three schemas. Either:
  - temporarily connect with a role that has `CREATE` on the database
    (Neon's `neondb_owner`) for the first deploy, **or**
  - pre-create them once as a privileged role, then grant usage:

    ```sql
    CREATE SCHEMA IF NOT EXISTS rag_shared;
    CREATE SCHEMA IF NOT EXISTS rag_level2_writer;
    CREATE SCHEMA IF NOT EXISTS rag_level3_chatbot;
    CREATE EXTENSION IF NOT EXISTS vector;
    GRANT USAGE, CREATE ON SCHEMA rag_shared, rag_level2_writer, rag_level3_chatbot TO rag_service_user;
    ```

The startup migration (`alembic upgrade head`, run by the Dockerfile
`CMD`) creates any missing schema **only when the role has the
privilege** and otherwise fails with a clear
`permission denied for database` — see [alembic/env.py](alembic/env.py)
`_ensure_managed_schemas()`.

---

## 6. Persistent storage (optional but recommended)

Uploaded original files are written to `STORAGE_LOCAL_PATH`
(`/app/storage`). Without a volume, that path is **ephemeral** — wiped
on every redeploy.

- Chunks and embeddings live in **Postgres**, so search and RAG chat keep
  working after a redeploy regardless.
- Only the **"download original file"** feature 404s if the volume is
  missing.

To persist originals:

1. rag-service service → **Settings** → **Volumes** → **New Volume**.
2. **Mount path:** `/app/storage`.
3. Redeploy.

You can skip this for the MVP and add it later without code changes.

---

## 7. First deploy + verification

1. Trigger the deploy (Railway does this automatically once variables are
   set, or hit **Deploy**).
2. Watch the **Deploy Logs**. On a healthy boot you should see, in order:
   - `alembic ... running upgrade` (or nothing extra if already at head),
   - `[rag-service] DB ping OK`,
   - `Uvicorn running on http://0.0.0.0:<PORT>`.
3. Railway marks the service **Healthy** once `/api/health/live` returns
   200 (configured in `railway.toml`).

Verify from your machine (replace with the real public URL Railway
assigns):

```powershell
$rag = "https://<rag-service>.up.railway.app"
# Liveness — should be 200 {"status":"alive",...}
Invoke-RestMethod "$rag/api/health/live"
# Readiness — should be 200 {"status":"ready","database":"ok"}
Invoke-RestMethod "$rag/api/health/ready"
```

If `/ready` returns 503, the DB is unreachable → re-check `DATABASE_URL`.

---

## 8. Point the writer backend at rag-service

Now tell the already-deployed **writer** service where rag-service lives.
On the **writer** service's Variables panel:

| Variable                  | Value                                                                            |
| ------------------------- | -------------------------------------------------------------------------------- |
| `RAG_SERVICE_URL`         | `https://<rag-service>.up.railway.app`                                           |
| `RAG_INTERNAL_JWT_SECRET` | _(the SAME secret set as rag-service `INTERNAL_JWT_SECRET`)_                     |
| `RAG_APP_ID`              | `level-2-writer` _(already the code default — set only if you want it explicit)_ |

Then **redeploy the writer service** so it picks up the new variables.

---

## 9. End-to-end check

1. Open <https://ai-writing-assistant.pages.dev>, log in.
2. Click the **+** (attach) button and upload a small PDF/DOCX/TXT.
3. Expected: a **201 Created** (not 503), the document appears, and its
   status becomes `ready` after ingestion.

---

## 10. Troubleshooting

| Symptom                                          | Likely cause                    | Fix                                                                                                               |
| ------------------------------------------------ | ------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Browser still 503 on upload                      | writer can't reach rag-service  | Check writer `RAG_SERVICE_URL` points to the live rag-service URL; confirm rag-service `/api/health/live` is 200. |
| Upload returns 401                               | secret mismatch                 | `INTERNAL_JWT_SECRET` (rag) ≠ `RAG_INTERNAL_JWT_SECRET` (writer). Set identical values, redeploy both.            |
| Boot crash: `schema "rag_shared" does not exist` | fresh DB, role lacks CREATE     | Pre-create schemas / grant CREATE (§5).                                                                           |
| Boot crash: `permission denied for database`     | role lacks CREATE on a fresh DB | Same as above (§5).                                                                                               |
| `/api/health/ready` = 503                        | DB unreachable                  | Verify `DATABASE_URL` host/password; confirm Neon compute is awake.                                               |
| Downloaded original 404s after redeploy          | no storage volume               | Mount a volume at `/app/storage` (§6).                                                                            |
