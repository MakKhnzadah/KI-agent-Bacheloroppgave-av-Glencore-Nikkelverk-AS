# Runbook (lokal MVP)

## 1) Installer
- Opprett venv og installer: `pip install -e .`
- Kopier `.env.example` til `.env` og fyll inn API-nøkler.

## 2) Kjør pipeline
- `ki-agent ingest data/uploads`
- `ki-agent suggest`
- `ki-agent review`
- `ki-agent apply`
- `ki-agent build-html`

## Output
- Rå kunnskap: `knowledge_base/raw`
- Generert HTML: `knowledge_base/html`
- Forslag/artefakter: `data/suggestions`, `data/normalized`
