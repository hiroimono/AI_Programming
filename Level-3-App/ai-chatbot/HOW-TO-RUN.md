# AI Chatbot SaaS (Level-3) — How to Run

Three services: **backend** (API), **admin** (management panel), **widget** (embeddable chat).
Port map: backend `8200`, admin `4202`, widget `5173`.

## Easiest way: VS Code Tasks

`Ctrl+Shift+P` → **Tasks: Run Task** → pick:

- `App 3: Backend (FastAPI)` — API only
- `App 3: Admin (Angular)` — admin panel only
- `App 3: Widget (Vite)` — widget only
- `App 3: Start AI-Chatbot-App` — starts all three in parallel

## Manual run (PowerShell)

### Backend (port 8200)

```powershell
Set-Location "Level-3-App/ai-chatbot/backend"
& ./venv/Scripts/Activate.ps1
uvicorn chatbot.main:app --reload --reload-exclude storage --port 8200
```

- `chatbot.main:app` = FastAPI app entry
- `--reload-exclude storage` = don't restart the server when uploads land in `storage/`
- First time: `pip install -r requirements.txt` (with venv active)
- DB migration: `alembic upgrade head`

### Admin panel (port 4202)

```powershell
Set-Location "Level-3-App/ai-chatbot/admin"
ng serve --port 4202
```

- First time: `npm install`
- In dev, `apiBase` = `http://localhost:8200` (see `src/environments/environment.development.ts`)
- The backend must be **running** for register/login to work.

### Widget (port 5173)

```powershell
Set-Location "Level-3-App/ai-chatbot/widget"
npm run dev
```

- First time: `npm install`

## Common issues

- **Register/login "failed" in admin** → backend is down. Start the backend first (port 8200).
- **CORS error** → backend `.env` `CORS_ORIGINS` must include the admin origin (`http://localhost:4202`).
