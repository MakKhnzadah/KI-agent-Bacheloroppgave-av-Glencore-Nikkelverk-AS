# Vector database (framtidig / ikke i MVP)

Dette dokumentet beskriver en mulig framtidig komponent for *vector database* (embeddings + lagring) som kan brukes til:

- Semantisk søk over kunnskapsbanken (CLI, senere chatbot)
- Gjenfinning av relevant kontekst ved forslag-generering (RAG) i fremtidig iterasjon

## MVP-beslutning
I denne forenklede MVP-en er vector DB **ikke inkludert**. Dette holdes som et forslag til videre arbeid.

## Konfigurasjon og kommandoer
Ikke relevant for MVP (ingen `index-kb`/`search`-kommandoer i CLI).

## Videre arbeid (anbefalt)
- Token-basert chunking (for mer stabile embeddings)
- Metadata-struktur for drift (kilde, prosess, område, versjon, gyldighet)
- Bruke gjenfinning til å foreslå *hvilket dokument* som skal oppdateres, og begrunne med sitater
