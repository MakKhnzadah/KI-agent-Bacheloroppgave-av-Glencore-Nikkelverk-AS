# Krav (utledet fra prosjektteksten)

## Funksjonelle krav (MVP)
- **FR1 Upload dokumenter**: Ekspertbruker kan levere ett eller flere dokumenter (PDF/Office/tekst/e-postutdrag).
- **FR2 Parse & normaliser**: Agenten konverterer innhold til normalisert tekst/struktur (f.eks. Markdown) og bevarer kildereferanser.
- **FR3 Generer forslag**: Agenten foreslår endringer i kunnskapsbanken (nye seksjoner, oppdaterte beskrivelser, metadata).
- **FR4 Review**: Ekspertbruker kan se forslag (diff/summary), og enten **godkjenne** eller **avvise**.
- **FR5 Lagre**: Godkjente forslag brukes til å oppdatere kunnskapsbanken automatisk (filbasert repo: Markdown + YAML front matter).
- **FR6 HTML**: Kunnskapsbanken kan genereres til HTML for lesing i nettleser.

## Ikke-funksjonelle krav (anbefalt)
- **NFR1 Sporbarhet**: Hvert kunnskapsdokument bør ha metadata for kilde(r), dato, versjon og forfatter/ansvarlig rolle.
- **NFR2 Reproduserbarhet**: Pipeline skal kunne kjøres på nytt og gi samme resultat gitt samme input.
- **NFR3 Versjonering**: Endringer lagres via Git (eller tilsvarende), slik at man kan se historikk og rulle tilbake.
- **NFR4 Tilgang**: Skrive = ekspertbrukere. Lese = alle ansatte. (For MVP kan dette være rollebasert policy i dokumentasjon.)
- **NFR5 Sikkerhet**: Ingen hemmelige nøkler i repo; bruk `.env`/Key Vault ved Azure.

## Leveranser
1. **KI-agent (MVP)** som implementerer flyten: upload → parse/normaliser → forslag → godkjenning → lagring.
2. **Kunnskapsbank** i råformat + **HTML-versjon**.
3. **Dokumentasjon** + forslag til videreutvikling (f.eks. chatbot-integrasjon).
