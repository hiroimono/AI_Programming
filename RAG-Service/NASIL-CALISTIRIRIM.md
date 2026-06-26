# RAG Service — Nasıl Çalıştırırım?

> **Hızlı özet:** FastAPI mikroservisi, port **8100**.
> Tek bir terminal, tek bir komut.

## Ön koşullar (bir kerelik)

- Python 3.12+ kurulu (`python --version`).
- `RAG-Service/venv/` zaten var (yoksa: `cd RAG-Service; python -m venv venv; .\venv\Scripts\Activate.ps1; pip install -r requirements.txt`).
- `.env` dosyası `.env.example`'dan kopyalanmış (Faz 0'da içi neredeyse boş, sorun değil).

## Başlatma

```powershell
cd RAG-Service
.\venv\Scripts\Activate.ps1
uvicorn rag_service.main:app --reload --port 8100
```

Hazır olduğunda terminalde: `Application startup complete`.

## Doğrulama

| Servis | URL |
|---|---|
| Health | <http://localhost:8100/api/health> |
| Swagger UI | <http://localhost:8100/docs> |
| ReDoc | <http://localhost:8100/redoc> |

`/api/health` cevabı: `{"status":"ok","service":"rag-service","version":"0.1.0"}`

## Durdurma

`Ctrl + C`.

## Tek tıkla alternatif (VS Code)

`Ctrl + Shift + P` → **Tasks: Run Task** → **RAG Service: Start**.

## Hangi app'lerle birlikte çalışır?

- **Level-2 (AI Writing Assistant):** Faz 5'ten itibaren mecburi (doküman upload + chat).
- **Level-3+ (gelecek):** Mecburi.
- **Tek başına test:** Postman / curl ile direkt rag-service'i çağırabilirsin (Faz 4'ten sonra).

## Hangi fazda neyi yapıyor?

| Faz | RAG Service yetenekleri |
|---|---|
| 0 (şu an) | Sadece `/api/health`. |
| 1-2 | Neon bağlantısı + Alembic tablolar. |
| 3 | Parser/chunker/embedder/retriever modülleri (henüz endpoint yok). |
| 4 | `/api/rag/documents`, `/api/rag/search` aktif. |
| 5+ | Level-2 BE bu servise istek atıyor. |

## Mimari referansları

- TR: `Documents/Strategy Documents/4.1 RAG Mikroservis Mimarisi ve Schema-per-App Yaklaşımı (TR).md`
- EN: `Documents/Strategy Documents/4.2 RAG Microservice Architecture and Schema-per-App Approach (EN).md`
