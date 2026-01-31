# Datamodell (praktisk filbasert)

## Kunnskapsdokument (Markdown + YAML front matter)
Hvert dokument er en `.md`-fil i `knowledge_base/raw`.

**Anbefalte metadatafelt**
- `id`: stabil ID (slug)
- `title`: tittel
- `tags`: liste
- `area`: f.eks. "raffinering", "HMS", "vedlikehold"
- `version`: semver eller dato-basert
- `last_reviewed`: ISO-dato
- `owner_role`: f.eks. "prosessingeniør"
- `sources`: liste med kildereferanser (filnavn, url, e-post-id, etc.)
- `confidence`: valgfritt (0–1) for hvor sikker teksten er

## Forslag (Suggestion)
Forslag lagres som JSON i `data/suggestions/` (generert, ikke i Git).

Minste felt
- `suggestion_id`
- `created_at`
- `target_path`: hvilken `.md` som endres
- `operation`: `create` | `update` | `append_section`
- `proposed_markdown`: foreslått innhold
- `rationale`: kort begrunnelse
- `citations`: referanser til inputkilder (side/avsnitt hvis mulig)

## Normalisert tekst (internt)
Normaliserte mellomprodukter kan lagres i `data/normalized/` for sporbarhet.
