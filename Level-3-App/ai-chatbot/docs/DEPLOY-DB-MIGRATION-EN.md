# Production DB Migration Guide (EN) — Level-3 Chatbot

> **PREPARE-ONLY.** This describes how to promote schema changes to the
> production Neon database. **No migration is run against production here.**
> You execute every command below yourself, after reading it.

---

## 1. Current state

- Migration tool: **Alembic** (async, `alembic/env.py` reads `DATABASE_URL`).
- Single head revision: **`0001_initial`** (`down_revision = None`). It:
  - enables the `vector` (pgvector) and `pgcrypto` extensions,
  - creates all tables (bots, bot_configs, documents, chunks, conversations,
    messages, usage_events, tenants, admin_users, …),
  - applies `ENABLE + FORCE ROW LEVEL SECURITY` + a `tenant_isolation` policy.
- The chunk-embedding vector dimension is pinned to the embedding model
  (`OPENAI_EMBEDDING_DIM=1536`). Changing the model is a data migration
  (re-embed everything), not just a schema bump.

Verify the local head before touching prod:

```bash
# From backend/
alembic heads      # expect a single head: 0001_initial (head)
alembic history    # linear history, no branches/multiple heads
```

Multiple heads = a merge migration is needed first (`alembic merge`). Never
deploy a divergent history to prod.

---

## 2. Roles: migration vs runtime (recommended split)

| Purpose | Role | Privileges |
|---------|------|-----------|
| Migrations / DDL | owner role (e.g. `ai_chatbot_owner`) | full DDL, can create extensions |
| App runtime (`DATABASE_URL` in Railway) | **new** non-owner role | DML only, **`NOBYPASSRLS`** |

Today the app runs as the owner role, which **bypasses RLS** — tenant
isolation currently relies solely on app-level `WHERE tenant_id` filters. As
part of go-live, create a dedicated runtime role so RLS becomes real
defense-in-depth:

```sql
-- Run ONCE against the prod DB as the owner (review before executing).
CREATE ROLE chatbot_app LOGIN PASSWORD '<generate-a-strong-one>' NOBYPASSRLS;
GRANT USAGE ON SCHEMA public TO chatbot_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO chatbot_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO chatbot_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO chatbot_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO chatbot_app;
```

Then set Railway's `DATABASE_URL` to use `chatbot_app`, and keep the owner
connection string only for running migrations. (Tracked as a follow-up; not
strictly required for M8 to function, but required for RLS to actually protect
tenants.)

---

## 3. Neon promotion strategy (branch → production)

Neon supports **branching** — use it as a safe pre-flight and instant backup.

1. **Branch prod** into a throwaway branch (`migration-test`). This is a
   copy-on-write snapshot — effectively a free, instant backup point.
2. Point a temporary `DATABASE_URL` at the **branch** and run the migration
   there first (steps in §4). Smoke-test the app against the branch.
3. If green, run the same migration against **production**.
4. If it goes wrong, you still have the pre-migration branch to restore from
   (or reset prod to the branch).

Neon branches live in the same **Frankfurt** region — no data leaves the EU.

---

## 4. Applying a migration (you run these)

```bash
# From backend/, with DATABASE_URL pointing at the TARGET (branch first, then prod).

# 4a. DRY RUN — generate the SQL offline and READ it before running anything.
alembic upgrade head --sql > migration_review.sql
#    Review migration_review.sql: confirm extensions, tables, and RLS policies
#    match expectations and nothing destructive is present.

# 4b. Confirm extensions exist on the target (owner role):
#     CREATE EXTENSION IF NOT EXISTS vector;
#     CREATE EXTENSION IF NOT EXISTS pgcrypto;
#     (0001_initial does this, but Neon may require them pre-enabled.)

# 4c. Apply for real (owner role connection):
alembic upgrade head

# 4d. Verify:
alembic current           # should print 0001_initial (head)
```

Run 4a–4d against the **branch** first, then repeat against **production**.

---

## 5. Rollback

- **Schema rollback:** `alembic downgrade -1` (or `alembic downgrade base` to
  drop everything). ⚠️ Destructive — it drops tables/data. Only meaningful
  right after a bad migration, before real traffic.
- **Preferred on Neon:** don't downgrade — **restore from the pre-migration
  branch** (§3). Point the app back at the good branch or reset prod to it.
  This is faster and non-destructive.
- Always take the Neon branch snapshot (§3.1) **before** any prod migration so
  a clean restore point exists.

---

## 6. Pre-flight checklist

- [ ] `alembic heads` shows a single head (no divergent history)
- [ ] `alembic upgrade head --sql` reviewed; no unexpected destructive DDL
- [ ] Neon **branch snapshot** of prod taken (restore point)
- [ ] `vector` + `pgcrypto` extensions available on the target
- [ ] Migration applied to the **branch** and smoke-tested first
- [ ] (Recommended) dedicated `NOBYPASSRLS` runtime role created; `DATABASE_URL`
      switched to it; owner kept for migrations only
- [ ] Migration applied to **production**; `alembic current` == head
- [ ] App boots against prod; `/api/health/ready` green
