# Level-3 Chatbot — Yol Haritası ve Karar Takibi (Living Doc)

> Milestone durumu + **ertelenen/gelecek kararların** takibi. Her milestone
> başında/sonunda güncellenir. Son güncelleme: **M8 sonu**.

---

## Milestone durumu (thin-slice, M0→M8)

| # | Kapsam | Durum | Commit |
|---|---|---|---|
| **M0** | Scaffold + DB foundation (10 tablo, RLS, extensions) | ✅ | `8ebaa6b`/`d766ddc` |
| **M1** | Tenant/admin auth plane (register/login/me, JWT, argon2) | ✅ 9/9 test | `491b989` |
| **M2** | Bot + BotConfig CRUD (tenant-scoped, RLS izolasyon) | ✅ 9/9 test | `9a395f3` |
| **M3** | RAG training: upload→storage→parse/chunk/embed/store | ✅ 9/9 test | `d567961` |
| **M4** | Widget auth plane (widget/preview scope, Origin whitelist) | ✅ 10/10 test | `511b016` |
| **M5** | Chat SSE: retrieve→guards→moderation→LLM stream→citations→UsageEvent | ✅ 8/8 test | `b27c137` |
| **M6** | Widget (Shadow DOM, SSE, mobile-first) | ✅ | `5e1ca46` |
| **M7** | Admin paneli (Angular 21, Material 3) | ✅ | `—` |
| **M8** | Cila + deploy hazırlığı (rate limit, moderation, PII; Railway EU + Cloudflare Pages, Neon promotion) | ✅ | A `619f812` · B `0618b9b` · C `acb39d9` · D `c6db049` · E `8bdd27b` |

---

## M6 notları (teslim edildi)

- **Widget (Lit + Shadow DOM):** style-izole edilebilir embed script. Güvenli config'i
  `GET /api/widget/config` ile yükler, session'ı `POST /api/widget/session` ile açar
  (embed `bot_id` + `tenant_id` taşır), sonra chat'i `POST /api/widget/chat` üzerinden
  stream eder (SSE, `fetch` + `ReadableStream` ile tüketilir).
- **Mobile-first:** önce base style, sonra `@media (min-width: …)` ile büyük ekran.
- **SSE tüketimi:** `event: … / data: …` frame'lerini parse et → `meta` (conversation_id,
  message_id) → `sources` (citation) → çok sayıda `delta` (metni ekle) → `done` | `error`.
  Turn devamlılığı için `conversation_id`'yi client'ta sakla.
- **Origin whitelist:** widget'ın gerçek Origin'i server-side olarak `Bot.allowed_domains`
  ile doğrulanır (boş liste = MVP'de allow-all).
- **Config asla secret sızdırmaz:** `WidgetConfigOut` `system_prompt`, `model`,
  `temperature` içermez — bunlar server-side kalır.

---

## M8 notları (teslim edildi — ince dilimler A–E)

- **Dilim A — teknik rate limiting (`619f812`):** slowapi IP-başına limitler
  (login 5/dk, register 10/saat, widget session 10/dk, widget chat 30/dk),
  hepsi `.env`'den ayarlanabilir, in-memory depo. auth/widget/chat router'larından
  `from __future__ import annotations` kaldırıldı ki FastAPI, slowapi'nin `@wraps`
  wrapper'ı altında Pydantic body param'larını doğru çözsün. Bu plan-bazlı kota
  **DEĞİL** — o, `Tenant.plan` + `UsageEvent` üzerinden gelecek billing fazı işi.
- **Dilim B — input moderation (`0618b9b`):** her kullanıcı mesajı retrieval/LLM
  **öncesi** OpenAI `omni-moderation-latest` ile taranır. Flagged turn'ler hazır
  bir refusal alır, `status="blocked"` ile saklanır ve **UsageEvent kaydetmez**
  (model çağrısı yok = maliyet yok). `moderate()` **fail-open** — moderation
  kesintisi chat'i düşürmez. Config: `moderation_enabled`, `moderation_refusal_message`.
- **Dilim C — PII redaction (`acb39d9`):** `chatbot/redact.py` regex ile
  email/telefon/kredi kartı/IBAN'ı typed placeholder'a çevirir. **Sadece
  saklanan** mesaj içeriğine uygulanır (user turn + assistant answer) —
  retrieval/LLM hâlâ ham metni görür. DB audit trail + logları PII'siz tutar
  (GDPR). Presidio fazla ağır bulunup elendi; `redact()` swappable seam.
- **Dilim D — deploy artefaktları, SADECE HAZIRLIK (`c6db049`):** backend
  `Dockerfile` (non-root, PORT-bound uvicorn, HEALTHCHECK) + `.dockerignore` +
  `railway.json`; admin `public/_redirects` (Angular SPA fallback);
  `docs/DEPLOY-EN.md`/`-TR.md`. 3-birim topoloji (backend→Railway/Amsterdam,
  admin→Cloudflare Pages, widget→CDN), Neon Frankfurt. **Gerçek deploy yapılmadı.**
- **Dilim E — prod DB migration hazırlığı, SADECE HAZIRLIK (`8bdd27b`):**
  `docs/DEPLOY-DB-MIGRATION-EN.md`/`-TR.md`. Tek head `0001_initial`,
  owner-vs-`NOBYPASSRLS`-runtime rol ayrımı, Neon branch→production promotion,
  offline SQL dry-run, branch-restore rollback. **Prod'a migration çalıştırılmadı.**

> İşaretlenen prod takipleri (blocker değil, aşağıda izleniyor): Railway geçici
> FS'i `storage/` için volume ister; in-memory rate limit tek replica'yı aşınca
> Redis ister; app DB rolü şu an **RLS'i bypass ediyor** (izolasyon app-level
> `WHERE tenant_id`'ye bağlı) — yayında ayrı runtime rolüyle düzelt.

---

## Ertelenen kararlar (deferred — tool-seam bırakıldı)

| Konu | Karar | Not / seam |
|---|---|---|
| **Native mobil** (madde 3.1) | Level-4 backlog'a ERTELENDİ | MVP = responsive/mobile-first web + (belki) admin PWA |
| **Text-to-SQL / müşteri DB sorgu** (madde 8) | ERTELENDİ | Chat pipeline'da **tool-seam** hazırla: `retrieve_context` bir "tool" gibi dursun; `query_database` sonra eklensin |
| **Ayrı B2B CDN/gateway** (FORK A önü) | İLERİDE | Ürün-önü katman; iş mantığı taşımaz |
| **RAG-Service konsolidasyonu** | İLERİDE | Embedder/Retriever Protocol seam'leri hazır; prod'a dokunma |
| **Register gating** | MVP'de public self-service | Sonra invite/admin-only **ayrı endpoint** olarak kilitlenebilir (geri dönüşü kolay) |

---

## Açık sorular / gelecekte netleşecek

- [ ] Quota/plan enforcement nerede? (`Tenant.plan` var; free/paid limitleri **gelecek billing fazı**, M8 değil — M8 yalnızca teknik IP-başına rate limiting getirdi.)
- [ ] Stripe metered billing export (`UsageEvent.cost_usd` hazır) — Phase 6.
- [x] Moderation + PII redaction katmanı — **M8'de tamam**: OpenAI `omni-moderation-latest` input gate (Dilim B) + saklanan içerikte regex PII redaction (Dilim C).
- [x] Widget Origin whitelist doğrulama (`Bot.allowed_domains`) — M4'te tamam (`_origin_allowed`, boş liste = allow-all).
- [x] Preview conversation'lar (`is_preview=true`) quota/analytics'ten dışlanıyor — M5'te doğrulandı (preview turn'de `UsageEvent` yok).
- [x] Prod DB migration stratejisi (Neon branch → production) — **M8 Dilim E'de belgelendi** (`DEPLOY-DB-MIGRATION-TR.md`). Alembic-CI hâlâ açık.
- [ ] **RLS-bypass düzeltmesi:** `DATABASE_URL` için ayrı `NOBYPASSRLS` runtime rolü oluştur ki RLS tenant'ları gerçekten izole etsin (owner rol migration'da kalır). SQL Dilim E dokümanlarında; yayında çalıştır.

---

## Uyum / operasyon (kalıcı kısıt)

- **İkamet: Almanya → GDPR/ePrivacy.** Cloud region **EU** (Frankfurt/Amsterdam).
  Neon EU + Railway EU + Cloudflare Pages.
- **Git:** asla otomatik commit yok; her commit onay ister ("commit" denirse onaylı).
  Her faza temiz working tree ile başla.
- **Terminal (oh-my-posh):** fresh PowerShell ilk komutta `^U` prepend bozulması
  yapıyor → ilk komut hata verir, retry çözer. `cd` yerine `Set-Location`
  (bazen "not recognized" — retry). venv Python: `& ".\venv\Scripts\python.exe"`.
