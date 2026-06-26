# Level-2 — AI Writing Assistant — Nasıl Çalıştırırım?

> **Hızlı özet:** Backend (FastAPI) port **8001**, Frontend (Angular) port **4201**, Gateway (.NET) port **5000/5001**.
> Üç terminal açıp her birinde aşağıdaki tek satırı çalıştır.

## Ön koşullar (bir kerelik)

- Python 3.12+ kurulu (`python --version`).
- Node 20+ ve Angular CLI kurulu (`ng version`).
- .NET 9 SDK kurulu (`dotnet --version`).
- `backend/venv/` zaten var (yoksa: `cd backend; python -m venv venv; .\venv\Scripts\Activate.ps1; pip install -r requirements.txt`).
- Gateway kurulu (Gateway/RUN.md'ye bak).
- `backend/.env` içinde `OPENAI_API_KEY=sk-...` set edili.

## Gateway (.NET, port 5000/5001)

Level-2 auth + konuşma DB'si için Gateway'i ÖNCE başlat:

```powershell
cd Gateway\src\Gateway.API
dotnet run
```

Hazır olduğunda: `Now listening on: https://localhost:5001`.

## Backend (FastAPI SSE, port 8001)

Yeni bir terminalde:

```powershell
cd Level-2-App\ai-writing-assistant\backend
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8001
```

Hazır olduğunda: `Application startup complete`.

## Frontend (Angular, port 4201)

Yeni bir terminalde:

```powershell
cd Level-2-App\ai-writing-assistant\frontend
ng serve --port 4201
```

Hazır olduğunda: `Application bundle generation complete`.

## Doğrulama

| Servis          | URL                              |
| --------------- | -------------------------------- |
| Gateway Swagger | <https://localhost:5001/swagger> |
| Backend Swagger | <http://localhost:8001/docs>     |
| Frontend        | <http://localhost:4201>          |

## Durdurma

Her terminalde `Ctrl + C`.

## Tek tıkla alternatif (VS Code)

`Ctrl + Shift + P` → **Tasks: Run Task** → **App 2: Start AI-Writing-Assistant-App**.
(Bu görev backend + frontend + gateway'i paralel başlatır.)

## RAG eklentisi geldiğinde (Faz 5+)

`RAG-Service` da paralel başlatılmalı. O zaman 4. terminal:

```powershell
cd RAG-Service
.\venv\Scripts\Activate.ps1
uvicorn rag_service.main:app --reload --port 8100
```
