# Level-3 Chatbot — Roadmap and Decision Tracking (Living Doc)

> Milestone status + tracking of **deferred/future decisions**. Updated at the
> start/end of every milestone. Last update: **end of M8**.

---

## Milestone status (thin-slice, M0→M8)

| # | Scope | Status | Commit |
|---|---|---|---|
| **M0** | Scaffold + DB foundation (10 tables, RLS, extensions) | ✅ | `8ebaa6b`/`d766ddc` |
| **M1** | Tenant/admin auth plane (register/login/me, JWT, argon2) | ✅ 9/9 tests | `491b989` |
| **M2** | Bot + BotConfig CRUD (tenant-scoped, RLS isolation) | ✅ 9/9 tests | `9a395f3` |
| **M3** | RAG training: upload→storage→parse/chunk/embed/store | ✅ 9/9 tests | `d567961` |
| **M4** | Widget auth plane (widget/preview scope, Origin whitelist) | ✅ 10/10 tests | `511b016` |
| **M5** | Chat SSE: retrieve→guards→moderation→LLM stream→citations→UsageEvent | ✅ 8/8 tests | `b27c137` |
| **M6** | Widget (Shadow DOM, SSE, mobile-first) | ✅ | `5e1ca46` |
| **M7** | Admin panel (Angular 21, Material 3) | ✅ | `—` |
| **M8** | Polish + deploy prep (rate limit, moderation, PII; Railway EU + Cloudflare Pages, Neon promotion) | ✅ | A `619f812` · B `0618b9b` · C `acb39d9` · D `c6db049` · E `8bdd27b` |

---

## M6 notes (delivered)

- **Widget (Lit + Shadow DOM):** style-isolated embeddable script. Loads safe config
  via `GET /api/widget/config`, opens a session via `POST /api/widget/session`
  (embed carries `bot_id` + `tenant_id`), then streams chat over
  `POST /api/widget/chat` (SSE, consumed with `fetch` + `ReadableStream`).
- **Mobile-first:** base styles first, `@media (min-width: …)` for larger screens.
- **SSE consumption:** parse `event: … / data: …` frames → `meta` (conversation_id,
  message_id) → `sources` (citations) → many `delta` (append text) → `done` | `error`.
  Persist `conversation_id` client-side for turn continuity.
- **Origin whitelist:** the widget's real Origin is enforced server-side against
  `Bot.allowed_domains` (empty list = allow-all in the MVP).
- **Config never leaks secrets:** `WidgetConfigOut` excludes `system_prompt`, `model`,
  `temperature` — those stay server-side.

---

## M8 notes (delivered — thin slices A–E)

- **Slice A — technical rate limiting (`619f812`):** slowapi per-IP caps (login
  5/min, register 10/hour, widget session 10/min, widget chat 30/min), all
  `.env`-tunable, in-memory storage. Removed `from __future__ import annotations`
  from the auth/widget/chat routers so FastAPI resolves Pydantic body params
  correctly under slowapi's `@wraps` wrapper. **NOT** plan-based quota — that is
  a future billing-phase feature keyed on `Tenant.plan` + `UsageEvent`.
- **Slice B — input moderation (`0618b9b`):** each user message is screened by
  OpenAI `omni-moderation-latest` **before** retrieval/LLM. Flagged turns get a
  canned refusal, persist with `status="blocked"`, and record **no** UsageEvent
  (no model call = no cost). `moderate()` **fails open** so a moderation outage
  never takes chat down. Config: `moderation_enabled`, `moderation_refusal_message`.
- **Slice C — PII redaction (`acb39d9`):** `chatbot/redact.py` regex-scrubs
  email/phone/credit-card/IBAN into typed placeholders. Applied **only to stored**
  message content (user turn + assistant answer) — retrieval/LLM still see the raw
  text. Keeps the DB audit trail + logs PII-free (GDPR). Presidio rejected as
  overkill; `redact()` is a swappable seam.
- **Slice D — deploy artifacts, PREPARE-ONLY (`c6db049`):** backend `Dockerfile`
  (non-root, PORT-bound uvicorn, HEALTHCHECK) + `.dockerignore` + `railway.json`;
  admin `public/_redirects` (Angular SPA fallback); `docs/DEPLOY-EN.md`/`-TR.md`.
  3-unit topology (backend→Railway/Amsterdam, admin→Cloudflare Pages, widget→CDN),
  Neon Frankfurt. **No real deploy performed.**
- **Slice E — prod DB migration prep, PREPARE-ONLY (`8bdd27b`):**
  `docs/DEPLOY-DB-MIGRATION-EN.md`/`-TR.md`. Single head `0001_initial`,
  owner-vs-`NOBYPASSRLS`-runtime role split, Neon branch→production promotion,
  offline SQL dry-run, branch-restore rollback. **No migration run against prod.**

> Flagged prod follow-ups (not blockers, tracked below): ephemeral Railway FS
> needs a volume for `storage/`; in-memory rate limit needs Redis past one
> replica; the app DB role currently **bypasses RLS** (isolation relies on
> app-level `WHERE tenant_id`) — fix with a dedicated runtime role at go-live.

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

- [ ] Where is quota/plan enforcement? (`Tenant.plan` exists; free/paid limits are a **future billing phase**, not M8 — M8 shipped only technical per-IP rate limiting.)
- [ ] Stripe metered billing export (`UsageEvent.cost_usd` ready) — Phase 6.
- [x] Moderation + PII redaction layer — **done in M8**: OpenAI `omni-moderation-latest` input gate (Slice B) + regex PII redaction on stored content (Slice C).
- [x] Widget Origin whitelist validation (`Bot.allowed_domains`) — done in M4 (`_origin_allowed`, empty list = allow-all).
- [x] Preview conversations (`is_preview=true`) excluded from quota/analytics — verified in M5 (no `UsageEvent` on preview turns).
- [x] Prod DB migration strategy (Neon branch → production) — **documented in M8 Slice E** (`DEPLOY-DB-MIGRATION-EN.md`). Alembic-in-CI still open.
- [ ] **RLS-bypass fix:** create a dedicated `NOBYPASSRLS` runtime role for `DATABASE_URL` so RLS actually isolates tenants (owner role kept for migrations). SQL provided in Slice E docs; execute at go-live.

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
