# AI Chatbot SaaS (Level-3) — Nasıl Çalıştırırım

Üç servis var: **backend** (API), **admin** (yönetim paneli), **widget** (gömülebilir sohbet).
Port haritası: backend `8200`, admin `4202`, widget `5173`.

## En kolay yol: VS Code Task'ları

`Ctrl+Shift+P` → **Tasks: Run Task** → seç:

- `App 3: Backend (FastAPI)` — sadece API
- `App 3: Admin (Angular)` — sadece admin paneli
- `App 3: Widget (Vite)` — sadece widget
- `App 3: Start AI-Chatbot-App` — üçünü birden paralel başlatır

## Elle çalıştırma (PowerShell)

### Backend (port 8200)

```powershell
Set-Location "Level-3-App/ai-chatbot/backend"
& ./venv/Scripts/Activate.ps1
uvicorn chatbot.main:app --reload --reload-exclude storage --port 8200
```

- `chatbot.main:app` = FastAPI uygulama girişi
- `--reload-exclude storage` = upload'lar `storage/`'a yazınca sunucu yeniden başlamasın
- İlk kez: `pip install -r requirements.txt` (venv aktifken)
- DB migration: `alembic upgrade head`

### Admin paneli (port 4202)

```powershell
Set-Location "Level-3-App/ai-chatbot/admin"
ng serve --port 4202
```

- İlk kez: `npm install`
- Dev'de `apiBase` = `http://localhost:8200` (bkz. `src/environments/environment.development.ts`)
- Register/login çalışması için backend'in **açık** olması şart.

### Widget (port 5173)

```powershell
Set-Location "Level-3-App/ai-chatbot/widget"
npm run dev
```

- İlk kez: `npm install`

## Sık karşılaşılan hata

- **Admin'de register/login "failed"** → backend kapalı. Önce backend'i başlat (port 8200).
- **CORS hatası** → backend `.env` içindeki `CORS_ORIGINS` admin origin'ini (`http://localhost:4202`) içermeli.
