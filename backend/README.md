## How to run the backend (FastAPI)

### Prerequisites
- Python 3.x installed
- (Optional) Ollama running locally if you want AI features

### 1) Create + activate venv (repo root)
PowerShell (Windows):
```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
```

### 2) Install dependencies
From repo root:
```powershell
pip install -r backend\requirements.txt
```

If you created your venv inside `backend\venv` and are running commands from the `backend` folder:
```powershell
python -m pip install -r requirements.txt
```

### 3) Start the API
From repo root:
```powershell
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

Open:
- http://127.0.0.1:8000/health
- http://127.0.0.1:8000/docs

### Notes
- If PowerShell blocks activation scripts, you can run: `Set-ExecutionPolicy -Scope Process Bypass` (then re-run activation).
