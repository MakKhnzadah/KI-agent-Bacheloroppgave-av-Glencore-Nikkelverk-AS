/**
 * Mock Data for Glencore Knowledge Management System
 */

import { Document, Activity } from "@/types";

export const mockDocuments: Document[] = [
  {
    id: "1",
    title: "Sikkerhetsprosedyre Smelteverk 2026",
    fileName: "sikkerhet_smelteverk_2026.pdf",
    category: "Sikkerhet",
    status: "pending",
    uploadedBy: "Maria Hansen",
    uploadedAt: "10. feb 2026 - 14:30",
    originalContent: `Sikkerhetsprosedyre for Smelteverk

1. Alle medarbeidere må bruke verneutstyr
2. Temperaturovervåking skal sjekkes hver time
3. Nødutganger må være fri til enhver tid

Ved avvik fra normal drift:
- Stopp prosessen umiddelbart
- Varsle vaktleder`,
    revisedContent: `Sikkerhetsprosedyre for Smelteverk - Oppdatert 2026

1. Alle medarbeidere må bruke komplett verneutstyr inkludert hjelm, briller og hansker
2. Temperaturovervåking skal sjekkes hver 30. minutt og logges digitalt
3. Nødutganger må være fri og tydelig merket til enhver tid
4. Brannslukkingsutstyr skal kontrolleres ukentlig

Ved avvik fra normal drift:
- Stopp prosessen umiddelbart
- Varsle vaktleder og HMS-ansvarlig
- Dokumenter hendelsen i avvikssystemet`,
  },
  {
    id: "2",
    title: "Vedlikeholdsplan Elektrolyse Q1 2026",
    fileName: "vedlikehold_elektrolyse_q1.pdf",
    category: "Vedlikehold",
    status: "pending",
    uploadedBy: "Erik Berg",
    uploadedAt: "9. feb 2026 - 09:15",
    originalContent: `Vedlikeholdsplan Elektrolyse Q1

Ukentlig:
- Inspeksjon av elektroder
- Kontroll av strømforsyning

Månedlig:
- Kalibrering av målerutstyr
- Rengjøring av filtre`,
    revisedContent: `Vedlikeholdsplan Elektrolyse Q1 2026 - Revidert

Daglig:
- Visuell inspeksjon av elektrodesystem
- Loggføring av driftsparametre

Ukentlig:
- Detaljert inspeksjon av elektroder
- Kontroll av strømforsyning og sikringer
- Test av alarmsystemer

Månedlig:
- Kalibrering av alle målerutstyr
- Rengjøring og utskifting av filtre
- Kontroll av kjølesystem

Kvartalsvis:
- Omfattende systemsjekk
- Oppdatering av dokumentasjon`,
  },
  {
    id: "3",
    title: "Miljørapport Utslipp Januar 2026",
    fileName: "miljo_rapport_jan2026.pdf",
    category: "Miljø",
    status: "pending",
    uploadedBy: "Johan Olsen",
    uploadedAt: "8. feb 2026 - 16:45",
    originalContent: `Miljørapport Januar 2026

Utslipp til luft: Innenfor grenseverdier
Utslipp til vann: Godkjent nivå
Avfallshåndtering: 65% resirkulering

Konklusjon: Akseptabelt nivå`,
    revisedContent: `Miljørapport - Januar 2026 (Detaljert)

Utslipp til luft:
- SO2: 45 mg/Nm³ (grense: 50 mg/Nm³) ✓
- NOx: 78 mg/Nm³ (grense: 100 mg/Nm³) ✓
- Støv: 12 mg/Nm³ (grense: 20 mg/Nm³) ✓

Utslipp til vann:
- pH-verdi: 7.2 (akseptabelt område) ✓
- Tungmetaller: Under deteksjonsgrense ✓
- Temperatur: 18°C (grense: 25°C) ✓

Avfallshåndtering:
- Total avfall: 450 tonn
- Resirkulert: 293 tonn (65%)
- Mål for Q1: Øke til 70%

Konklusjon: Alle verdier innenfor godkjente grenser. Foreslår tiltak for å øke resirkuleringsgrad.

Anbefalinger:
- Implementere sorteringsstasjon for metallavfall
- Øke frekvens på miljøovervåking`,
  },
  {
    id: "4",
    title: "Kvalitetskontroll Raffinering Q4 2025",
    fileName: "kvalitet_raffinering_q4.pdf",
    category: "Kvalitet",
    status: "approved",
    uploadedBy: "Lars Andersen",
    uploadedAt: "5. feb 2026 - 11:20",
    originalContent: `Kvalitetskontroll Q4 2025

Nikkelrenhet: 99.8%
Produksjon: 12,500 tonn
Avvik: 2 hendelser`,
    revisedContent: `Kvalitetskontroll Raffinering - Q4 2025 (Fullstendig Rapport)

Nikkelrenhet:
- Gjennomsnitt: 99.8%
- Målsetning: 99.7%
- Status: Over forventet kvalitet ✓

Produksjonsvolum:
- Total produksjon: 12,500 tonn
- Planlagt: 12,000 tonn
- Avvik: +4.2% (positivt)

Kvalitetsavvik:
- Totalt 2 hendelser registrert
- Hendelse 1: Liten variasjon i renhet (99.65%)
- Hendelse 2: Forsinkelse i prosess (løst)
- Korrigerende tiltak implementert

Konklusjon: Meget godt resultat for Q4 2025`,
    approvedContent: `Kvalitetskontroll Raffinering - Q4 2025 (Fullstendig Rapport)

Nikkelrenhet:
- Gjennomsnitt: 99.8%
- Målsetning: 99.7%
- Status: Over forventet kvalitet ✓

Produksjonsvolum:
- Total produksjon: 12,500 tonn
- Planlagt: 12,000 tonn
- Avvik: +4.2% (positivt)

Kvalitetsavvik:
- Totalt 2 hendelser registrert
- Hendelse 1: Liten variasjon i renhet (99.65%)
- Hendelse 2: Forsinkelse i prosess (løst)
- Korrigerende tiltak implementert

Konklusjon: Meget godt resultat for Q4 2025`,
  },
  {
    id: "5",
    title: "Prosedyre for Nødstans",
    fileName: "nodstopp_prosedyre.pdf",
    category: "Sikkerhet",
    status: "approved",
    uploadedBy: "Kari Nilsen",
    uploadedAt: "3. feb 2026 - 13:45",
    originalContent: `Nødstans Prosedyre

1. Trykk rød nødstoppknapp
2. Evakuer området
3. Ring vaktleder`,
    revisedContent: `Prosedyre for Nødstans - Komplett Veiledning

1. Aktivering av Nødstans:
   - Trykk nærmeste røde nødstoppknapp
   - Bekreft at alarmen aktiveres
   - Vent på systembekreftelse

2. Evakuering:
   - Forlat området umiddelbart via nærmeste nødutgang
   - Hjelp kollegaer som trenger assistanse
   - Samles ved oppsamlingspunkt

3. Varsling:
   - Ring vaktleder: 555-1000
   - Ring HMS-ansvarlig: 555-1001
   - Ved behov: Ring 110/112/113

4. Oppfølging:
   - Ikke retur til området før klarsignal
   - Delta i hendelsesrapportering
   - Følg vaktleders instruksjoner`,
    approvedContent: `Prosedyre for Nødstans - Komplett Veiledning

1. Aktivering av Nødstans:
   - Trykk nærmeste røde nødstoppknapp
   - Bekreft at alarmen aktiveres
   - Vent på systembekreftelse

2. Evakuering:
   - Forlat området umiddelbart via nærmeste nødutgang
   - Hjelp kollegaer som trenger assistanse
   - Samles ved oppsamlingspunkt

3. Varsling:
   - Ring vaktleder: 555-1000
   - Ring HMS-ansvarlig: 555-1001
   - Ved behov: Ring 110/112/113

4. Oppfølging:
   - Ikke retur til området før klarsignal
   - Delta i hendelsesrapportering
   - Følg vaktleders instruksjoner`,
  },
  {
    id: "6",
    title: "Opplæringsplan Nye Medarbeidere",
    fileName: "opplaering_nye.pdf",
    category: "Prosedyre",
    status: "approved",
    uploadedBy: "Per Sørensen",
    uploadedAt: "1. feb 2026 - 10:00",
    originalContent: `Opplæring for Nye Medarbeidere

Uke 1: Sikkerhet
Uke 2: Produksjon
Uke 3: Kvalitet`,
    revisedContent: `Komplett Opplæringsplan - Nye Medarbeidere 2026

Uke 1 - HMS og Sikkerhet:
- Dag 1-2: Grunnleggende HMS-opplæring
- Dag 3: Verneutstyr og bruk
- Dag 4: Nødprosedyrer og evakuering
- Dag 5: Test og sertifisering

Uke 2 - Produksjonsprosesser:
- Dag 1-2: Introduksjon til raffineringsprosess
- Dag 3: Kvalitetskontroll
- Dag 4: Utstyr og vedlikehold
- Dag 5: Praktisk trening

Uke 3 - Kvalitet og Systemer:
- Dag 1-2: Kvalitetsstyringssystemer
- Dag 3: Dokumenthåndtering
- Dag 4: Miljøprosedyrer
- Dag 5: Evaluering og oppfølging

Uke 4 - Praktisk Opplæring:
- Supervisert arbeid med erfaren kollega
- Gradvis økende ansvar
- Daglig evaluering`,
    approvedContent: `Komplett Opplæringsplan - Nye Medarbeidere 2026

Uke 1 - HMS og Sikkerhet:
- Dag 1-2: Grunnleggende HMS-opplæring
- Dag 3: Verneutstyr og bruk
- Dag 4: Nødprosedyrer og evakuering
- Dag 5: Test og sertifisering

Uke 2 - Produksjonsprosesser:
- Dag 1-2: Introduksjon til raffineringsprosess
- Dag 3: Kvalitetskontroll
- Dag 4: Utstyr og vedlikehold
- Dag 5: Praktisk trening

Uke 3 - Kvalitet og Systemer:
- Dag 1-2: Kvalitetsstyringssystemer
- Dag 3: Dokumenthåndtering
- Dag 4: Miljøprosedyrer
- Dag 5: Evaluering og oppfølging

Uke 4 - Praktisk Opplæring:
- Supervisert arbeid med erfaren kollega
- Gradvis økende ansvar
- Daglig evaluering`,
  },
  {
    id: "7",
    title: "Avfallshåndtering Farlig Avfall",
    fileName: "farlig_avfall.pdf",
    category: "Miljø",
    status: "rejected",
    uploadedBy: "Ola Johansen",
    uploadedAt: "28. jan 2026 - 15:30",
    originalContent: `Farlig Avfall

Sorter avfall i riktig container
Marker tydelig`,
    revisedContent: `Prosedyre for Håndtering av Farlig Avfall - Detaljert

1. Identifikasjon av Farlig Avfall:
   - Kjemisk avfall
   - Oljeforurensede materialer
   - Batterier og elektronikk
   - Asbestholdige materialer

2. Sortering:
   - Bruk godkjente containere
   - Sorter etter avfallstype
   - Ikke bland ulike typer

3. Merking:
   - Tydelig merking med innhold
   - Dato for deponering
   - Ansvarlig person

4. Lagring:
   - Godkjent lagringsområde
   - Sikret mot lekkasje
   - Regelmessig inspeksjon`,
  },
];

export const mockActivities: Activity[] = [
  {
    id: "1",
    type: "document_approved",
    title: "Nytt dokument godkjent",
    description: "Prosedyre for elektrolyse-vedlikehold",
    user: "Erik Berg",
    time: "15 minutter siden",
    documentId: "2",
  },
  {
    id: "2",
    type: "ai_suggestion",
    title: "KI-forslag klar",
    description: "Oppdatering: Sikkerhetsprosedyrer smelteovn",
    user: "System",
    time: "2 timer",
    documentId: "1",
  },
  {
    id: "3",
    type: "document_uploaded",
    title: "Dokument lastet opp",
    description: "Kvalitetskontroll raffinering Q4 2025",
    user: "Maria Hansen",
    time: "4 timer",
    documentId: "4",
  },
  {
    id: "4",
    type: "document_approved",
    title: "Nytt dokument godkjent",
    description: "Vedlikeholdsrutiner for filtreringssystem",
    user: "Johan Olsen",
    time: "1 dag",
    documentId: "5",
  },
  {
    id: "5",
    type: "document_rejected",
    title: "Dokument avvist",
    description: "Avfallshåndtering - trenger mer detaljer",
    user: "Kari Nilsen",
    time: "2 dager",
    documentId: "7",
  },
];

// Mock users for authentication
export const mockUsers = [
  {
    id: "1",
    name: "Admin User",
    email: "admin@glencore.com",
    password: "admin123",
    role: "admin" as const,
    department: "IT",
  },
  {
    id: "2",
    name: "Maria Hansen",
    email: "maria@glencore.com",
    password: "maria123",
    role: "user" as const,
    department: "Produksjon",
  },
  {
    id: "3",
    name: "Erik Berg",
    email: "erik@glencore.com",
    password: "erik123",
    role: "user" as const,
    department: "Vedlikehold",
  },
];
