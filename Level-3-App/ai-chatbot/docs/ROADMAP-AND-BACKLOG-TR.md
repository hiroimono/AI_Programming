# Level-3 Chatbot — Yol Haritası ve Karar Takibi (Living Doc)

> Milestone durumu + **ertelenen/gelecek kararların** takibi. Her milestone
> başında/sonunda güncellenir. Son güncelleme: **M5 sonu**.

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
| **M7** | Admin panel (Angular 21, Material 3) | ✅ current | `—` |
| **M8** | Polish + deploy (slowapi, PII, moderation; Railway EU + Cloudflare Pages) | ⬜ sıradaki | — |

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

- [ ] Quota/plan enforcement nerede? (`Tenant.plan` var; free/paid limitleri M8?)
- [ ] Stripe metered billing export (`UsageEvent.cost_usd` hazır) — Phase 6.
- [ ] Moderation + PII redaction katmanı — sağlayıcı TBD; `_moderate` no-op seam M5'te bağlandı, gerçek sağlayıcı M8'de.
- [x] Widget Origin whitelist doğrulama (`Bot.allowed_domains`) — M4'te tamam (`_origin_allowed`, boş liste = allow-all).
- [x] Preview conversation'lar (`is_preview=true`) quota/analytics'ten dışlanıyor — M5'te doğrulandı (preview turn'de `UsageEvent` yok).
- [ ] Prod DB migration stratejisi (Neon branch → production) + Alembic CI.

---

## Uyum / operasyon (kalıcı kısıt)

- **İkamet: Almanya → GDPR/ePrivacy.** Cloud region **EU** (Frankfurt/Amsterdam).
  Neon EU + Railway EU + Cloudflare Pages.
- **Git:** asla otomatik commit yok; her commit onay ister ("commit" denirse onaylı).
  Her faza temiz working tree ile başla.
- **Terminal (oh-my-posh):** fresh PowerShell ilk komutta `^U` prepend bozulması
  yapıyor → ilk komut hata verir, retry çözer. `cd` yerine `Set-Location`
  (bazen "not recognized" — retry). venv Python: `& ".\venv\Scripts\python.exe"`.
