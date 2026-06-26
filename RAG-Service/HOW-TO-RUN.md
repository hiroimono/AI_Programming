# RAG Service — How to Run

> **Quick reference:** FastAPI microservice, port **8100**.
> One terminal, one command.

## Prerequisites (one-time)

- Python 3.12+ installed (`python --version`).
- `RAG-Service/venv/` already exists (if not: `cd RAG-Service; python -m venv venv; .\venv\Scripts\Activate.ps1; pip install -r requirements.txt`).
- `.env` copied from `.env.example` (mostly empty in Phase 0, that's fine).

## Start

```powershell
cd RAG-Service
.\venv\Scripts\Activate.ps1
uvicorn rag_service.main:app --reload --port 8100
```

Ready when the terminal shows: `Application startup complete`.

## Verify

| Service    | URL                                |
| ---------- | ---------------------------------- |
| Health     | <http://localhost:8100/api/health> |
| Swagger UI | <http://localhost:8100/docs>       |
| ReDoc      | <http://localhost:8100/redoc>      |

`/api/health` response: `{"status":"ok","service":"rag-service","version":"0.1.0"}`

## Stop

`Ctrl + C`.

## One-click alternative (VS Code)

`Ctrl + Shift + P` → **Tasks: Run Task** → **RAG Service: Start**.

## Which apps require it?

- **Level-2 (AI Writing Assistant):** Required from Phase 5 onward (document upload + chat).
- **Level-3+ (upcoming):** Required.
- **Standalone testing:** You can hit rag-service directly via Postman / curl (from Phase 4 onward).

## What does it do per phase?

| Phase   | RAG Service capability                                              |
| ------- | ------------------------------------------------------------------- |
| 0 (now) | `/api/health` only.                                                 |
| 1-2     | Neon connection + Alembic tables.                                   |
| 3       | Parser / chunker / embedder / retriever modules (no endpoints yet). |
| 4       | `/api/rag/documents` and `/api/rag/search` live.                    |
| 5+      | Level-2 BE calls this service.                                      |

## Architecture references

- TR: `Documents/Strategy Documents/4.1 RAG Mikroservis Mimarisi ve Schema-per-App Yaklaşımı (TR).md`
- EN: `Documents/Strategy Documents/4.2 RAG Microservice Architecture and Schema-per-App Approach (EN).md`
