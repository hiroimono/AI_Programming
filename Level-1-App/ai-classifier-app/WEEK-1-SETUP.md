# Week 1 — Setup Guide

## 1. Python Installation

### Step 1: Download and Install Python

1. Go to https://www.python.org/downloads/
2. Click the **"Download Python 3.12.x"** button
3. Run the downloaded `.exe` file
4. ⚠️ **IMPORTANT:** Check **"Add Python to PATH"** on the first screen!
5. Click "Install Now"

> 💡 If you don't have admin rights on a company computer:
>
> - Select "Customize installation"
> - UNCHECK "Install for all users" (installs only for your user)
> - Choose an install path like `C:\Users\YOUR_USERNAME\Python312`

### Step 2: Verify Installation

Close and reopen the VS Code terminal (for PATH refresh), then:

```powershell
python --version
# Output: Python 3.12.x

pip --version
# Output: pip 24.x.x from ...
```

If both work, Python is ready.

---

## 2. Install Backend Dependencies

### Step 1: Create a Virtual Environment

In .NET, each project carries its own NuGet packages. Same concept in Python:
**Virtual Environment** = project-specific package isolation.

```powershell
# Navigate to the project folder
cd C:\Users\heltutan\Desktop\AI_Programming\Level-1-App\ai-classifier-app\backend

# Create virtual environment (think of it like dotnet restore)
python -m venv venv

# Activate the virtual environment
.\venv\Scripts\Activate.ps1
```

> ⚠️ If `Activate.ps1` doesn't work in PowerShell:
>
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```
>
> Run this command, then try again.

If activation is successful, you'll see `(venv)` at the beginning of the terminal line:

```text
(venv) PS C:\...\backend>
```

### Step 2: Install Packages

```powershell
# Install all packages from requirements.txt (like NuGet restore)
pip install -r requirements.txt
```

This command will install:

- **fastapi** → Web framework (equivalent of ASP.NET Core)
- **uvicorn** → ASGI server (equivalent of Kestrel)
- **openai** → OpenAI Python SDK
- **pydantic** → Data validation (equivalent of DataAnnotations)
- **python-dotenv** → Reading .env files (equivalent of appsettings.json)

---

## 3. OpenAI API Key Configuration

```powershell
# Create .env file in the backend folder
copy .env.example .env
```

Open the `.env` file and paste your API key:

```text
OPENAI_API_KEY=sk-paste-your-key-here
```

---

## 4. Run the Backend

```powershell
# Make sure the virtual environment is active ((venv) should appear at the start)
uvicorn main:app --reload --port 8000
```

Open in browser: http://localhost:8000/docs
→ Swagger UI will appear (just like Swagger in .NET!)

---

## 5. Create Angular Frontend

Open a new terminal (keep the backend running):

```powershell
cd C:\Users\heltutan\Desktop\AI_Programming\Level-1-App\ai-classifier-app

# Create Angular project
ng new frontend --style=css --routing=false --ssr=false

cd frontend

# Start the application
ng serve
```

Open in browser: http://localhost:4200

---

## 6. Checklist

If everything is working correctly:

- [ ] `python --version` → shows 3.11 or higher
- [ ] `pip --version` → works
- [ ] Backend: http://localhost:8000/docs → Swagger opens
- [ ] Frontend: http://localhost:4200 → Angular page opens
- [ ] `.env` file has a valid OpenAI API key

All OK → You can start examining the backend code!
