# KI-agent og kunnskapsbank for prosesskunnskap  
**Prosjekt nr. 6 – Bachelor/Masteroppgave**

**Oppdragsgiver:** Glencore Nikkelverk AS  

---

## 📌 Prosjektbeskrivelse

Prosesskunnskap ved Glencore Nikkelverk AS er i dag spredt på mange ulike kilder og ofte personavhengig. Dette innebærer risiko for tap av kritisk kompetanse og gjør informasjon vanskelig tilgjengelig for ansatte.

Dette prosjektet har som mål å utvikle en **KI-basert agent kombinert med en strukturert kunnskapsbank** for å:
- bevare kritisk prosesskunnskap
- standardisere og kvalitetssikre dokumentasjon
- legge til rette for fremtidig bruk i semantisk søk og chatbot-løsninger

Prosjektet fokuserer på **produksjon, strukturering og vedlikehold av kunnskapsdokumenter**, ikke utvikling av ferdig søkegrensesnitt.

---

## 🎯 Mål og leveranser

Prosjektet består av to hoveddeler:

### A) KI-agent (MVP)

KI-agenten skal:
- ta imot ett eller flere dokumenter fra en fagbruker (ekspert)
- analysere innholdet ved hjelp av språkmodeller
- foreslå nye eller oppdaterte seksjoner i kunnskapsbanken
- sende forslagene tilbake til bruker for godkjenning
- automatisk oppdatere kunnskapsbanken etter godkjenning

**Teknologier (foreløpig):**
- Python
- Språkmodeller via Microsoft/OpenAI API
- Eventuelt OpenWebUI
- Azure-tjenester for lagring og prosessering (etter avklaring)

---

### B) Kunnskapsbank

Kunnskapsbanken består av:
- kvalitetssikrede dokumenter i åpent råformat  
  - Markdown + YAML (front matter) **eller**  
  - AsciiDoc (med støtte for LaTeX)
- strukturert innhold egnet for:
  - konvertering til HTML
  - fremtidig semantisk søk / chatbot
  - bruk som opplæringsmateriale («lærebok»)

Utvikling av chatbot eller brukergrensesnitt for søk er **ikke** del av oppgaven, men kan inngå i videre arbeid (master / større prosjekt).

---

## 🔄 Arbeidsflyt / Prosess

1. Ekspertbruker laster opp dokumenter  
   (PDF, Office-filer, tekst, e-postutdrag)
2. KI-agenten analyserer innholdet
3. Agenten foreslår:
   - ny dokumentstruktur
   - oppdaterte beskrivelser
   - metadata (YAML)
4. Bruker godkjenner eller avviser forslag
5. Godkjente endringer lagres i kunnskapsbanken

---

## 🛠️ Hva studentene skal gjøre og lære

### Kjerneoppgaver (felles)
- Utvikle Python-pipeline for import, parsing og normalisering av dokumenter
- Integrere språkmodeller for tekstforståelse og forslag
- Implementere godkjenningsflyt (forslag → godkjenning → lagring)
- Strukturere dokumenter med metadata (YAML / front matter)

---

### Bachelor – eksempler
- Parser for PDF / Office / e-post
- Dublettkontroll og enkel konfliktvarsling
- Generering av HTML-versjon av kunnskapsbanken

### Master – eksempler
- Evaluering av kvalitet og presisjon i KI-forslag
- Håndtering av motstridende informasjon
- Arkitekturforslag for fremtidig chatbot-integrasjon

---

## 👥 Hvem passer oppgaven for

### Primært
- **Bachelor – Dataingeniør / Datateknikk**  
  Parsering, API-integrasjon, dokumentstruktur
- **Master – Kunstig intelligens / IKT**  
  Agentlogikk, evaluering, arkitektur

### Sekundært
- Cybersikkerhet (tilgangsstyring, logging)
- Multimedieteknologi (enkel HTML-visning – opsjon)

**Forkunnskaper:**
- Python
- API-bruk
- Git
- Grunnleggende Azure-forståelse

---

## ⚙️ Rammer og forutsetninger

- **Data:** Interne dokumenter (PDF, Office, tekst, e-post)
- **Format:** Markdown + YAML eller AsciiDoc
- **Verktøy:** Python, språkmodeller via API, Azure-ressurser
- **Tilgang:**
  - Skrivetilgang: ekspertbrukere
  - Lesetilgang: alle ansatte
- **Veiledning:** Fagspesialister fra Glencore Nikkelverk AS

---

## 📊 KPI og leveranser

**KPI:**  
- Antall ord i kvalitetssikrede dokumenter i kunnskapsbanken

**Leveranser:**
1. KI-agent (MVP) for oppdatering av kunnskapsbank
2. Kunnskapsbank i valgt råformat + generert HTML-versjon
3. Dokumentasjon og forslag til videreutvikling  
   (f.eks. chatbot-grensesnitt)



