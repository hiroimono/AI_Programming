# Level-2 — AI Writing Assistant — How to Run

> **Quick reference:** Backend (FastAPI) port **8001**, Frontend (Angular) port **4201**, Gateway (.NET) port **5000/5001**.
> Open three terminals and run one line in each.

## Prerequisites (one-time)

- Python 3.12+ installed (`python --version`).
- Node 20+ and Angular CLI installed (`ng version`).
- .NET 9 SDK installed (`dotnet --version`).
- `backend/venv/` already exists (if not: `cd backend; python -m venv venv; .\venv\Scripts\Activate.ps1; pip install -r requirements.txt`).
- Gateway set up (see `Gateway/HOW-TO-RUN.md`).
- `backend/.env` has `OPENAI_API_KEY=sk-...` set.

## Gateway (.NET, port 5000/5001)

Level-2 needs Gateway for auth + conversation DB. Start it FIRST:

```powershell
cd Gateway\src\Gateway.API
dotnet run
```

Ready when you see: `Now listening on: https://localhost:5001`.

## Backend (FastAPI SSE, port 8001)

In a new terminal:

```powershell
cd Level-2-App\ai-writing-assistant\backend
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8001
```

Ready when: `Application startup complete`.

## Frontend (Angular, port 4201)

In a new terminal:

```powershell
cd Level-2-App\ai-writing-assistant\frontend
ng serve --port 4201
```

Ready when: `Application bundle generation complete`.

## Verify

| Service         | URL                              |
| --------------- | -------------------------------- |
| Gateway Swagger | <https://localhost:5001/swagger> |
| Backend Swagger | <http://localhost:8001/docs>     |
| Frontend        | <http://localhost:4201>          |

## Stop

`Ctrl + C` in each terminal.

## One-click alternative (VS Code)

`Ctrl + Shift + P` → **Tasks: Run Task** → **App 2: Start AI-Writing-Assistant-App**.
(That task starts backend + frontend + gateway in parallel.)

## When the RAG addon ships (Phase 5+)

`RAG-Service` also needs to run in parallel. Add a 4th terminal:

```powershell
cd RAG-Service
.\venv\Scripts\Activate.ps1
uvicorn rag_service.main:app --reload --port 8100
```
