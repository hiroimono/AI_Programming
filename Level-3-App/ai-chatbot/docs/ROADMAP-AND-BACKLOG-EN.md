# Level-3 Chatbot — Roadmap and Decision Tracking (Living Doc)

> Milestone status + tracking of **deferred/future decisions**. Updated at the
> start/end of every milestone. Last update: **end of M2**.

---

## Milestone status (thin-slice, M0→M8)

| # | Scope | Status | Commit |
|---|---|---|---|
| **M0** | Scaffold + DB foundation (10 tables, RLS, extensions) | ✅ | `8ebaa6b`/`d766ddc` |
| **M1** | Tenant/admin auth plane (register/login/me, JWT, argon2) | ✅ 9/9 tests | `491b989` |
| **M2** | Bot + BotConfig CRUD (tenant-scoped, RLS isolation) | ✅ 9/9 tests | `9a395f3` |
| **M3** | RAG training: upload→storage→parse/chunk/embed/store | ⬜ next | — |
| **M4** | Widget auth plane (widget/preview scope, Origin whitelist) | ⬜ | — |
| **M5** | Chat SSE: retrieve→guards→moderation→LLM stream→citations→UsageEvent | ⬜ | — |
| **M6** | Widget (Lit, Shadow DOM, mobile-first) | ⬜ | — |
| **M7** | Admin panel (Angular) | ⬜ | — |
| **M8** | Polish + deploy (slowapi, PII, moderation; Railway EU + Cloudflare Pages) | ⬜ | — |

---

## M3 prep notes (next)

- **Storage Protocol seam:** `storage.py` — local FS (dev) ↔ Cloudflare R2 (prod).
  `save(tenant_id, bot_id, file) -> storage_path`, `load(path) -> bytes`, `delete`.
- **Embedder Protocol seam:** OpenAI `text-embedding-3-small` (dim 1536); must be
  mockable in tests.
- **Pipeline:** upload → Document(status=uploaded) → parse (pypdf/python-docx/openpyxl)
  → chunk (tiktoken token-based) → embed (batch) → insert Chunk[] → Document(status=ready).
  On error → status=failed + error_message.
- **Write UsageEvent:** event_type=`document_upload` + `embedding`.
- **RLS:** documents/chunks are FORCE'd → run the whole pipeline inside a
  `set_current_tenant`-pinned transaction; don't forget to re-pin after commit on
  large embed batches.
- Endpoint sketch: `POST /api/bots/{bot_id}/documents` (multipart),
  `GET /api/bots/{bot_id}/documents`, `DELETE .../documents/{id}` (soft delete +
  chunk cleanup).

---

## Deferred decisions (tool-seams left in place)

| Topic | Decision | Note / seam |
|---|---|---|
| **Native mobile** (item 3.1) | DEFERRED to Level-4 backlog | MVP = responsive/mobile-first web + (maybe) admin PWA |
| **Text-to-SQL / customer DB query** (item 8) | DEFERRED | Prepare a **tool-seam** in the chat pipeline: `retrieve_context` acts like a "tool"; `query_database` added later |
| **Separate B2B CDN/gateway** (front of FORK A) | LATER | Product-facing layer; carries no business logic |
| **RAG-Service consolidation** | LATER | Embedder/Retriever Protocol seams ready; don't touch prod |
| **Register gating** | Public self-service in MVP | Later can be locked to invite/admin-only as a **separate endpoint** (easy to reverse) |

---

## Open questions / to be clarified later

- [ ] Where is quota/plan enforcement? (`Tenant.plan` exists; free/paid limits in M8?)
- [ ] Stripe metered billing export (`UsageEvent.cost_usd` ready) — Phase 6.
- [ ] Moderation + PII redaction layer (M5/M8) — which provider?
- [ ] Widget Origin whitelist validation (`Bot.allowed_domains`) — M4 widget session mint.
- [ ] Preview conversations (`is_preview=true`) excluded from quota/analytics — verify in M5.
- [ ] Prod DB migration strategy (Neon branch → production) + Alembic in CI.

---

## Compliance / operations (permanent constraints)

- **Residence: Germany → GDPR/ePrivacy.** Cloud region **EU** (Frankfurt/Amsterdam).
  Neon EU + Railway EU + Cloudflare Pages.
- **Git:** never auto-commit; every commit asks for approval (the word "commit" grants
  it). Start each phase with a clean working tree.
- **Terminal (oh-my-posh):** a fresh PowerShell corrupts the first command's first token
  with a `^U` prepend → the first command errors, a retry fixes it. Use `Set-Location`
  instead of `cd` (sometimes "not recognized" — retry). venv Python:
  `& ".\venv\Scripts\python.exe"`.
