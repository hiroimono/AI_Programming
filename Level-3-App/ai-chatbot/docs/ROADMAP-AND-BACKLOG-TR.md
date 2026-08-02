# Level-3 Chatbot — Yol Haritası ve Karar Takibi (Living Doc)

> Milestone durumu + **ertelenen/gelecek kararların** takibi. Her milestone
> başında/sonunda güncellenir. Son güncelleme: **M2 sonu**.

---

## Milestone durumu (thin-slice, M0→M8)

| # | Kapsam | Durum | Commit |
|---|---|---|---|
| **M0** | Scaffold + DB foundation (10 tablo, RLS, extensions) | ✅ | `8ebaa6b`/`d766ddc` |
| **M1** | Tenant/admin auth plane (register/login/me, JWT, argon2) | ✅ 9/9 test | `491b989` |
| **M2** | Bot + BotConfig CRUD (tenant-scoped, RLS izolasyon) | ✅ 9/9 test | `9a395f3` |
| **M3** | RAG training: upload→storage→parse/chunk/embed/store | ⬜ sıradaki | — |
| **M4** | Widget auth plane (widget/preview scope, Origin whitelist) | ⬜ | — |
| **M5** | Chat SSE: retrieve→guards→moderation→LLM stream→citations→UsageEvent | ⬜ | — |
| **M6** | Widget (Lit, Shadow DOM, mobile-first) | ⬜ | — |
| **M7** | Admin panel (Angular) | ⬜ | — |
| **M8** | Polish + deploy (slowapi, PII, moderation; Railway EU + Cloudflare Pages) | ⬜ | — |

---

## M3 için hazırlık notları (sıradaki)

- **Storage Protocol seam:** `storage.py` — local FS (dev) ↔ Cloudflare R2 (prod).
  `save(tenant_id, bot_id, file) -> storage_path`, `load(path) -> bytes`, `delete`.
- **Embedder Protocol seam:** OpenAI `text-embedding-3-small` (dim 1536); mock ile
  test edilebilir olsun.
- **Pipeline:** upload → Document(status=uploaded) → parse (pypdf/python-docx/openpyxl)
  → chunk (tiktoken token-based) → embed (batch) → Chunk[] insert → Document(status=ready).
  Hata → status=failed + error_message.
- **UsageEvent** yaz: event_type=`document_upload` + `embedding`.
- **RLS:** documents/chunks FORCE'lu → tüm pipeline `set_current_tenant` pinli
  transaction içinde; büyük embed batch'lerinde commit sonrası re-pin unutma.
- Endpoint taslağı: `POST /api/bots/{bot_id}/documents` (multipart),
  `GET /api/bots/{bot_id}/documents`, `DELETE .../documents/{id}` (soft delete +
  chunk temizliği).

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
- [ ] Moderation + PII redaction katmanı (M5/M8) — hangi sağlayıcı?
- [ ] Widget Origin whitelist doğrulama (`Bot.allowed_domains`) — M4 widget session mint.
- [ ] Preview conversation'lar (`is_preview=true`) quota/analytics'ten dışlanıyor — M5'te doğrula.
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
