# Level-3 Chatbot — Roadmap and Decision Tracking (Living Doc)

> Milestone status + tracking of **deferred/future decisions**. Updated at the
> start/end of every milestone. Last update: **end of M5**.

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
| **M7** | Admin panel (Angular 21, Material 3) | ✅ current | `—` |
| **M8** | Polish + deploy (slowapi, PII, moderation; Railway EU + Cloudflare Pages) | ⬜ next | — |

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
- [ ] Moderation + PII redaction layer — provider TBD; `_moderate` no-op seam wired in M5, real provider in M8.
- [x] Widget Origin whitelist validation (`Bot.allowed_domains`) — done in M4 (`_origin_allowed`, empty list = allow-all).
- [x] Preview conversations (`is_preview=true`) excluded from quota/analytics — verified in M5 (no `UsageEvent` on preview turns).
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
