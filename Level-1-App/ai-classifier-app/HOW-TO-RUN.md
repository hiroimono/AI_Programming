# Level-1 — AI Classifier App — How to Run

> **Quick reference:** Backend (FastAPI) port **8000**, Frontend (Angular) port **4200**.
> Open separate terminals and run one line in each.

## Prerequisites (one-time)

- Python 3.12+ installed (`python --version`).
- Node 20+ and Angular CLI installed (`ng version`).
- `backend/venv/` already exists (if not: `cd backend; python -m venv venv; .\venv\Scripts\Activate.ps1; pip install -r requirements.txt`).

## Backend (FastAPI, port 8000)

```powershell
cd Level-1-App\ai-classifier-app\backend
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload --reload-exclude output --port 8000
```

Ready when the terminal shows: `Application startup complete`.

## Frontend (Angular, port 4200)

In a new terminal:

```powershell
cd Level-1-App\ai-classifier-app\frontend
ng serve
```

Ready when: `Application bundle generation complete` and `http://localhost:4200`.

## Do I need the Gateway too?

**No.** Level-1 talks directly to its own backend. Gateway is only for apps that require auth.

## Verify

| Service | URL |
|---|---|
| Backend Swagger | <http://localhost:8000/docs> |
| Frontend | <http://localhost:4200> |

## Stop

`Ctrl + C` in each terminal.

## One-click alternative (VS Code)

`Ctrl + Shift + P` → **Tasks: Run Task** → **App 1: Start Al-Classifier-App**.
(That task starts backend + frontend + gateway in parallel.)
