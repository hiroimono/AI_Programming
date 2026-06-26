# Level-1 — AI Classifier App — Nasıl Çalıştırırım?

> **Hızlı özet:** Backend (FastAPI) port **8000**, Frontend (Angular) port **4200**.
> Üç ayrı terminal açıp her birinde aşağıdaki tek satırı çalıştır.

## Ön koşullar (bir kerelik)

- Python 3.12+ kurulu (`python --version`).
- Node 20+ ve Angular CLI kurulu (`ng version`).
- `backend/venv/` zaten var (yoksa: `cd backend; python -m venv venv; .\venv\Scripts\Activate.ps1; pip install -r requirements.txt`).

## Backend (FastAPI, port 8000)

```powershell
cd Level-1-App\ai-classifier-app\backend
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload --reload-exclude output --port 8000
```

Hazır olduğunda terminalde: `Application startup complete` görürsün.

## Frontend (Angular, port 4200)

Yeni bir terminalde:

```powershell
cd Level-1-App\ai-classifier-app\frontend
ng serve
```

Hazır olduğunda: `Application bundle generation complete` ve `http://localhost:4200`.

## Gateway de gerekiyor mu?

**Hayır.** Level-1 doğrudan kendi backend'ine bağlanır. Gateway sadece auth gerektiren uygulamalar için.

## Doğrulama

| Servis | URL |
|---|---|
| Backend Swagger | <http://localhost:8000/docs> |
| Frontend | <http://localhost:4200> |

## Durdurma

Her terminalde `Ctrl + C`.

## Tek tıkla alternatif (VS Code)

`Ctrl + Shift + P` → **Tasks: Run Task** → **App 1: Start Al-Classifier-App**.
(Bu görev backend + frontend + gateway'i paralel başlatır.)
