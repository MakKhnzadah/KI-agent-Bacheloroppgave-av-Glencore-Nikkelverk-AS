# Vector database (valgfritt)

Dette prosjektet har en valgfri komponent for *vector database* (embeddings + lagring) som kan brukes til:

- Semantisk søk over kunnskapsbanken (CLI, senere chatbot)
- Gjenfinning av relevant kontekst ved forslag-generering (RAG) i fremtidig iterasjon

## MVP-beslutning
I MVP er vector DB **ikke et krav**, men repoen støtter et lokalt oppsett med `chroma` (persist på disk) for å demonstrere end-to-end flyt.

## Konfigurasjon
Se `.env.example`.

Minstekrav for Chroma + OpenAI-kompatibel embeddings:

- `VECTOR_PROVIDER=chroma`
- `OPENAI_BASE_URL=https://api.openai.com` (eller OpenWebUI sin OpenAI-compatible base URL)
- `OPENAI_API_KEY=...`
- `OPENAI_EMBEDDING_MODEL=text-embedding-3-small`

## Kommandoer
- Indekser kunnskapsbanken: `ki-agent index-kb`
- Søk: `ki-agent search "spørring"`

## Videre arbeid (anbefalt)
- Token-basert chunking (for mer stabile embeddings)
- Metadata-struktur for drift (kilde, prosess, område, versjon, gyldighet)
- Støtte for andre backends (Azure AI Search, Qdrant, Pinecone)
- Bruke gjenfinning til å foreslå *hvilket dokument* som skal oppdateres, og begrunne med sitater
