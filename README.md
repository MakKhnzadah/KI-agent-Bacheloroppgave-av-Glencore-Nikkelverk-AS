# KI-agent og Kunnskapsbank for Prosesskunnskap

Prosjektet utvikler en KI-stottet arbeidsflyt for a hente ut, strukturere, kvalitetssikre og publisere prosesskunnskap for Glencore Nikkelverk AS.

Løsningen bestar av:
- et FastAPI-backend med dokumentbehandling, forslag/review/apply-flyt og vektorsok
- et React-frontend for innlogging, opplasting, review-kø og visning av kunnskapsbank
- lokal datalagring (SQLite + Chroma) for MVP-utvikling


## Prosjektmal

1. Fagbruker laster opp dokument/dokumenter 
2. Backend parser/normaliserer innhold
3. KI-tjeneste foreslar oppdateringer i kunnskapsbanken
4. Forslag reviewes (approved/rejected)
5. Godkjente forslag skrives til kunnskapsbanken
6. Vektorindeks oppdateres for semantisk sok

## Hurtigstart

### 1) Backend (FastAPI)

Fra repo-root:

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8001 --reload
```

Verifiser:
- API health: http://127.0.0.1:8001/health
- Swagger: http://127.0.0.1:8001/docs

### 2) Frontend (React + Vite)

Fra repo-root:

```powershell
cd frontend
npm install
npm run dev
```

