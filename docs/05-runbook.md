# Runbook (lokal MVP)

## 1) Installer
- Opprett venv (fra repo root):
	- `python -m venv .venv`
	- `. .\.venv\Scripts\Activate.ps1`
- Installer dependencies:
	- `pip install -r backend\requirements.txt`
- Kopier `.env.example` til `.env` og fyll inn API-nøkler (valgfritt for lokal Ollama).

## 2) Kjør pipeline
- Start API:
	- `uvicorn app.main:app --reload --app-dir backend`
- Åpne Swagger UI:
	- `http://127.0.0.1:8000/docs`
- Kjør use-case flyten via endepunkter:
	- `POST /documents/upload`
	- `GET /workflow/suggestions` (finn `suggestion_id`)
	- `POST /workflow/suggestions/{suggestion_id}/review`
	- `POST /workflow/suggestions/{suggestion_id}/apply`
	- `POST /kb/build-html`

## 3) Vector DB (lokal Chroma + Ollama embeddings)

### Forutsetninger
- Installer og start Ollama
- Last ned embedding-modell (default): `ollama pull nomic-embed-text`

Miljøvariabler (valgfritt):
- `OLLAMA_BASE_URL` (default: `http://localhost:11434`)
- `OLLAMA_EMBED_MODEL` (default: `nomic-embed-text`)
- `VECTOR_STORE_DIR` (default: `databases/vector_store/chroma`)

### Indekser kunnskapsbanken
Kunnskapsbankens kilde (source-of-truth) ligger i `databases/knowledge_base/raw/`.

Start API:
- `uvicorn app.main:app --reload --app-dir backend`

Indekser:
- `POST http://127.0.0.1:8000/vector/index/kb`

Søk:
- `GET  http://127.0.0.1:8000/vector/search?q=<sp%C3%B8rsm%C3%A5l>&k=5`

## 4) Workflow DB (SQLite) – forslag/review/historikk

For å lagre arbeidsflyt-data for MVP-en (opplastinger, forslag, review og enkel historikk) bruker vi en lokal SQLite database.

Miljøvariabler (valgfritt):
- `WORKFLOW_DB_PATH` (default: `databases/workflow/workflow.sqlite3`)

Tabeller (foreløpig):
- `uploads`
- `normalized_documents`
- `suggestions`
- `reviews`
- `applied_changes`

Databasen blir automatisk initialisert når API-et starter.

### Endepunkter (workflow)

Hent forslag:
- `GET  http://127.0.0.1:8000/workflow/suggestions/<suggestion_id>`

Godkjenn/avvis forslag:
- `POST http://127.0.0.1:8000/workflow/suggestions/<suggestion_id>/review`

Eksempel body:
```json
{
	"decision": "approved",
	"reviewer": "name",
	"comment": "looks good"
}
```

Bruk godkjent forslag og oppdater kunnskapsbanken (skriver en .md fil i `databases/knowledge_base/raw/`):
- `POST http://127.0.0.1:8000/workflow/suggestions/<suggestion_id>/apply`

Merk: Etter `apply` trigger API-et automatisk re-indeksering av kunnskapsbanken i Chroma (best-effort, kjøres i bakgrunnen).

Responsen fra `apply` inkluderer også `reindex: "scheduled"` for å indikere at re-indeksering er lagt i kø.

Valgfritt body (for å velge filnavn/sti):
```json
{
	"kb_path": "procedures/pump-a.md",
	"notes": "applied after review"
}
```

### Review / godkjenning (API)

Hent forslag:
- `GET http://127.0.0.1:8000/workflow/suggestions/<suggestion_id>`

Godkjenn/avvis forslag:
- `POST http://127.0.0.1:8000/workflow/suggestions/<suggestion_id>/review`
- Body (JSON):
	- `{ "decision": "approved", "reviewer": "<navn>", "comment": "<valgfritt>" }`
	- eller `{ "decision": "rejected", "reviewer": "<navn>", "comment": "<valgfritt>" }`

## Output
- Rå kunnskap: `databases/knowledge_base/raw`
- Generert HTML: `databases/knowledge_base/html`
- Forslag/artefakter: `databases/data/suggestions`, `databases/data/normalized`

## Lokal LLM (Ollama) – test og evaluering

Vi har valgt å kjøre LLM lokalt med **Ollama**, og teste **Llama 3** først. Dette gir bedre kontroll på data (interne dokumenter), lavere kostnader under utvikling og rask iterasjon.

### Mål
- Finne ut om modellen leverer gode forslag til kunnskapsbanken.
- Avdekke typiske feil (f.eks. hallusinasjoner eller feil struktur).
- Bestemme om vi skal fortsette med Llama 3, bytte modell, eller justere prompt/pipeline.

### Foreslått testoppsett (enkelt)
1. Velg et lite, realistisk testsett (f.eks. 10–20 dokumenter).
2. Definer 3–5 konkrete oppgaver som skal måles, for eksempel:
	 - Oppsummering av innhold
	 - Uthenting av prosess-steg / prosedyrer
	 - Forslag til oppdatering av eksisterende KB-seksjoner
	 - Forslag til nye KB-seksjoner
	 - Generering av metadata (tittel, tags, kilde, dato)
3. Kjør samme test på like input (samme dokumenter og samme prompts), slik at resultatene kan sammenlignes.

### Hva vi vurderer (sjekkliste)
- **Faktakorrekthet**: Unngår modellen å finne på informasjon?
- **Dekning**: Får den med viktige punkter?
- **Struktur**: Passer formatet med KB-krav (seksjoner, tydelige overskrifter, metadata)?
- **Språk**: Forståelig og konsistent (norsk + fagtermer).
- **Sporbarhet**: Refererer den til kilder/utdrag når det er mulig?

### Enkel mal for å logge resultater
Bruk gjerne en liten tabell/tekstlogg per test:

- Dokument: <filnavn/id>
- Oppgave: <oppsummering | uthenting | forslag | metadata>
- Modell: <llama3 ...>
- Prompt-versjon: <v1/v2>
- Resultat: <kort beskrivelse>
- Score (1–5):
	- Korrekthet: _
	- Dekning: _
	- Struktur: _
	- Språk: _
- Feil/risiko: <hallusinasjon, mangler, uklart, feil format>
- Tiltak: <endre prompt, gi mer kontekst, juster pipeline, bytt modell>
