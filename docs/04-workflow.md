# Workflow (end-to-end)

1. **Upload**: legg inputfiler i `data/uploads/` (eller angi via CLI).
2. **Parse/normalize**: trekk ut tekst, fjern støy, lag en normalisert representasjon.
3. **Suggest**: send normalisert tekst + relevante KB-deler til LLM og få forslag.
4. **Review**: vis forslag som diff/summary, la ekspert godkjenne/avvise.
5. **Apply**: skriv godkjente endringer til `knowledge_base/raw/`.
6. **Build HTML**: generer lesbar HTML til `knowledge_base/html/`.

MVP: dette kjøres som lokale CLI-kommandoer.
