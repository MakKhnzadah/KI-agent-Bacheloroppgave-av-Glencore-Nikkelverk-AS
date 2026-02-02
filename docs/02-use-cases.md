# Use cases (fra diagram + tekst)

## Aktører
- **Employee/User**: Leser kunnskapsbank (HTML).
- **Expert User**: Laster opp dokumenter, vurderer forslag, godkjenner/avviser, initierer lagring.
- **Language Model Service (OpenAI-kompatibel, evt. lokal)**: Tekstforståelse og forslag.
- **Storage/Repository (lokalt filsystem + Git)**: Lagring/versjonering av kunnskapsbank og forslag.
- **Document sources**: PDF/Office/e-post/tekst (input).

## Use cases
- **Login** *(include)*: Autentisering før review/approval (kan være out-of-scope i MVP; dokumenteres).
- **Upload documents**: Ekspert legger inn inputfiler.
- **Parse & normalize**: Agenten henter tekst, rydder, strukturerer, dedupliserer grovt.
- **Generate update suggestions**: Agenten lager forslag til endringer i kunnskapsbanken.
- **Review suggestions**: Ekspert ser forslag.
  - **Reject suggestion** *(extend)*: avviser forslag.
  - **Approve changes**: godkjenner forslag.
- **Save updates**: Godkjente forslag skrives til repo/lagring.
- **Read knowledge (HTML)**: Ansatte leser generert HTML.

## MVP-tolkning
For bachelor-MVP kan alle use cases kjøres via **CLI** (ingen web-UI). "Login" kan erstattes av lokal policy + Git-tilganger.
