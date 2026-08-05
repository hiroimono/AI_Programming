# Production DB Migration Rehberi (TR) — Level-3 Chatbot

> **SADECE HAZIRLIK.** Bu doküman, şema değişikliklerini production Neon
> veritabanına nasıl taşıyacağını anlatır. **Burada production'a karşı hiçbir
> migration çalıştırılmaz.** Aşağıdaki her komutu, okuduktan sonra sen
> çalıştırırsın.

---

## 1. Mevcut durum

- Migration aracı: **Alembic** (async, `alembic/env.py` `DATABASE_URL`'i okur).
- Tek head revizyonu: **`0001_initial`** (`down_revision = None`). Bu revizyon:
  - `vector` (pgvector) ve `pgcrypto` extension'larını etkinleştirir,
  - tüm tabloları oluşturur (bots, bot_configs, documents, chunks,
    conversations, messages, usage_events, tenants, admin_users, …),
  - `ENABLE + FORCE ROW LEVEL SECURITY` + `tenant_isolation` policy uygular.
- Chunk-embedding vector boyutu embedding modeline sabitlenmiştir
  (`OPENAI_EMBEDDING_DIM=1536`). Modeli değiştirmek şema değil, veri
  migration'ıdır (her şeyi yeniden embed etmek).

Prod'a dokunmadan önce lokal head'i doğrula:

```bash
# backend/ içinden
alembic heads      # tek head bekle: 0001_initial (head)
alembic history    # doğrusal geçmiş, branch/çoklu head yok
```

Çoklu head = önce merge migration gerekir (`alembic merge`). Ayrışmış geçmişi
ASLA prod'a deploy etme.

---

## 2. Roller: migration vs runtime (önerilen ayrım)

| Amaç | Rol | Yetkiler |
|------|-----|----------|
| Migration / DDL | owner rol (ör. `ai_chatbot_owner`) | tam DDL, extension oluşturabilir |
| App runtime (Railway'deki `DATABASE_URL`) | **yeni** non-owner rol | sadece DML, **`NOBYPASSRLS`** |

Bugün app owner rolüyle çalışıyor ve bu rol **RLS'i bypass ediyor** — tenant
izolasyonu şu an sadece app-level `WHERE tenant_id` filtrelerine bağlı. Yayına
alırken, RLS'in gerçek defense-in-depth olması için ayrı bir runtime rolü
oluştur:

```sql
-- Prod DB'de owner olarak BİR KEZ çalıştır (çalıştırmadan önce incele).
CREATE ROLE chatbot_app LOGIN PASSWORD '<güçlü-bir-tane-üret>' NOBYPASSRLS;
GRANT USAGE ON SCHEMA public TO chatbot_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO chatbot_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO chatbot_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO chatbot_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO chatbot_app;
```

Sonra Railway'in `DATABASE_URL`'ini `chatbot_app`'i kullanacak şekilde ayarla,
owner connection string'ini sadece migration için sakla. (Takip işi olarak
izleniyor; M8'in çalışması için şart değil ama RLS'in tenant'ları gerçekten
koruması için gerekli.)

---

## 3. Neon promotion stratejisi (branch → production)

Neon **branching** destekler — güvenli bir ön-uçuş ve anında yedek olarak kullan.

1. Prod'u tek kullanımlık bir branch'e (`migration-test`) **branch'le**. Bu
   copy-on-write snapshot'tır — pratikte ücretsiz, anlık bir yedek noktası.
2. Geçici bir `DATABASE_URL`'i **branch'e** yönelt, migration'ı önce orada
   çalıştır (§4 adımları). App'i branch'e karşı smoke-test et.
3. Yeşilse, aynı migration'ı **production**'a karşı çalıştır.
4. Ters giderse, geri yüklemek için hâlâ migration-öncesi branch elinde olur
   (veya prod'u branch'e reset'le).

Neon branch'leri aynı **Frankfurt** region'ında yaşar — hiçbir veri AB dışına
çıkmaz.

---

## 4. Migration uygulama (sen çalıştırırsın)

```bash
# backend/ içinden, DATABASE_URL HEDEFİ göstererek (önce branch, sonra prod).

# 4a. DRY RUN — SQL'i offline üret ve ÇALIŞTIRMADAN ÖNCE OKU.
alembic upgrade head --sql > migration_review.sql
#    migration_review.sql'i incele: extension'lar, tablolar ve RLS policy'ler
#    beklentiyle uyuşuyor mu, yıkıcı bir şey var mı doğrula.

# 4b. Hedefte extension'ların var olduğunu doğrula (owner rol):
#     CREATE EXTENSION IF NOT EXISTS vector;
#     CREATE EXTENSION IF NOT EXISTS pgcrypto;
#     (0001_initial bunu yapar ama Neon önceden etkin istemiş olabilir.)

# 4c. Gerçekten uygula (owner rol connection):
alembic upgrade head

# 4d. Doğrula:
alembic current           # 0001_initial (head) yazmalı
```

4a–4d'yi önce **branch**'e, sonra **production**'a karşı tekrarla.

---

## 5. Rollback

- **Şema rollback:** `alembic downgrade -1` (veya her şeyi drop etmek için
  `alembic downgrade base`). ⚠️ Yıkıcı — tablo/veri düşürür. Sadece kötü bir
  migration'dan hemen sonra, gerçek trafik gelmeden anlamlı.
- **Neon'da tercih edilen:** downgrade etme — **migration-öncesi branch'ten
  geri yükle** (§3). App'i iyi branch'e geri yönelt veya prod'u ona reset'le.
  Bu daha hızlı ve yıkıcı değil.
- Temiz bir geri-yükleme noktası olsun diye her prod migration'ından **önce**
  Neon branch snapshot'ını (§3.1) mutlaka al.

---

## 6. Ön-uçuş kontrol listesi

- [ ] `alembic heads` tek head gösteriyor (ayrışmış geçmiş yok)
- [ ] `alembic upgrade head --sql` incelendi; beklenmedik yıkıcı DDL yok
- [ ] Prod'un Neon **branch snapshot**'ı alındı (geri-yükleme noktası)
- [ ] Hedefte `vector` + `pgcrypto` extension'ları mevcut
- [ ] Migration önce **branch**'e uygulandı ve smoke-test edildi
- [ ] (Önerilen) ayrı `NOBYPASSRLS` runtime rolü oluşturuldu; `DATABASE_URL`
      ona geçirildi; owner sadece migration'da tutuldu
- [ ] Migration **production**'a uygulandı; `alembic current` == head
- [ ] App prod'a karşı boot ediyor; `/api/health/ready` yeşil
