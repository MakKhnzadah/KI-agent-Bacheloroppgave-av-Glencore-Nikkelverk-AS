import { Sidebar } from "@/app/components/sidebar";
import { useParams, useNavigate } from "react-router";
import { ArrowLeft, Download, FileText, Calendar, User, Eye } from "lucide-react";

export function DocumentDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const documents: Record<string, {
    title: string;
    author: string;
    date: string;
    category: string;
    wordCount: string;
    content: {
      title: string;
      sections: Array<{ heading: string; content: string }>;
      references: string[];
    };
  }> = {
    "1": {
      title: "Prosedyre for elektrolyse-vedlikehold",
      author: "Erik Berg",
      date: "15. jan 2026",
      category: "Vedlikehold",
      wordCount: "2,847 ord",
      content: {
        title: "Prosedyre for elektrolyse-vedlikehold",
        sections: [
          {
            heading: "1. Innledning",
            content: "Dette dokumentet beskriver standardprosedyrer for vedlikehold av elektrolyseceller ved Glencore Nikkelverk AS. Prosedyrene sikrer konsistent og sikker gjennomføring av vedlikeholdsarbeid."
          },
          {
            heading: "2. Formål",
            content: "Formålet med denne prosedyren er å sikre optimal drift av elektrolyseanlegg, samt å bevare kritisk kompetanse i organisasjonen gjennom dokumentert praksis."
          },
          {
            heading: "3. Temperaturkontroll",
            content: "Optimal temperatur skal ligge mellom 1250-1350°C basert på nyere prosessdata fra Q4 2025. Overvåkning skjer automatisk hvert minutt via SCADA-system, med automatiske varsler ved avvik."
          },
          {
            heading: "4. Sikkerhetsprosedyrer",
            content: "Før oppstart må personlig verneutstyr benyttes, arbeidsområdet må være sikret og skiltet i henhold til HMS-prosedyre 2026-01, og kommunikasjon med driftsleder må være etablert. Termografisk inspeksjon av elektroder er obligatorisk."
          },
          {
            heading: "5. Vedlikeholdsintervaller",
            content: "Vedlikehold skal utføres hver 4. måned eller ved observerte avvik. Inspeksjon av anoden skal gjøres med ultralydutstyr for nøyaktig måling av slitasje. Prediktivt vedlikehold basert på sensordata implementeres fra Q2 2026."
          },
          {
            heading: "6. Dokumentasjon",
            content: "Alt vedlikeholdsarbeid skal dokumenteres i det digitale vedlikeholdssystemet (Maximo) med dato, utført av, og eventuelle observasjoner. Bilder og målerapporter skal vedlegges."
          },
        ],
        references: [
          "ISO 9001:2015 - Kvalitetsstyring",
          "Internkontrollforskriften",
          "Glencore Sikkerhetshåndbok",
          "ISO 55000 - Asset Management",
          "HMS-prosedyre 2026-01"
        ]
      }
    },
    "2": {
      title: "Sikkerhetsprosedyrer smelteverk",
      author: "System",
      date: "12. jan 2026",
      category: "Sikkerhet",
      wordCount: "3,251 ord",
      content: {
        title: "Sikkerhetsprosedyrer for smelteverk",
        sections: [
          {
            heading: "1. Generelle sikkerhetskrav",
            content: "Alle ansatte som arbeider i smelteverket må ha gjennomført HMS-opplæring og være godkjent for arbeid i høytemperaturområder. Personlig verneutstyr er obligatorisk til enhver tid."
          },
          {
            heading: "2. Adgangskontroll",
            content: "Tilgang til smelteverket er begrenset til autorisert personell. Alle besøkende må ha følge av driftsansvarlig og må benytte besøkende-PVU."
          },
          {
            heading: "3. Nødprosedyrer",
            content: "Ved nødsituasjoner skal alarmen aktiveres umiddelbart. Evakueringsveier er tydelig merket og skal holdes fri til enhver tid. Samlingspunkt er ved hovedporten."
          },
          {
            heading: "4. Varme arbeider",
            content: "Alle varme arbeider krever arbeidstillatelse og skal koordineres med driftsleder. Brannvakt må være tilstede under og i minst 30 minutter etter avsluttet arbeid."
          },
        ],
        references: [
          "Internkontrollforskriften",
          "Glencore Sikkerhetshåndbok",
          "Arbeidsmiljøloven",
          "HMS-prosedyre 2026-01"
        ]
      }
    },
    "3": {
      title: "Kvalitetskontroll raffinering Q4 2025",
      author: "Maria Hansen",
      date: "11. jan 2026",
      category: "Prosesser",
      wordCount: "1,856 ord",
      content: {
        title: "Kvalitetskontroll raffinering Q4 2025",
        sections: [
          {
            heading: "1. Målsetning",
            content: "Kvalitetskontrollrapporten for Q4 2025 presenterer resultatene fra raffineringsprosessen og identifiserer forbedringsområder for kommende kvartal."
          },
          {
            heading: "2. Prøvetaking",
            content: "Prøver tas hver 4. time fra hovedstrømmen. Analyseresultater viser gjennomsnittlig renhetsgrad på 99.97%, som er innenfor spesifikasjon."
          },
          {
            heading: "3. Avvik og korrigerende tiltak",
            content: "To mindre avvik ble registrert i november, begge relatert til temperatursvingninger. Korrigerende tiltak ble iverksatt og problemer er løst."
          },
          {
            heading: "4. Konklusjon",
            content: "Raffineringsprosessen i Q4 2025 har vært stabil og resultater er tilfredsstillende. Fokusområder for Q1 2026 er ytterligere optimalisering av energiforbruk."
          },
        ],
        references: [
          "ISO 9001:2015 - Kvalitetsstyring",
          "Kvalitetsplan 2025",
          "Prosessrapport Q3 2025"
        ]
      }
    },
    "4": {
      title: "Vedlikeholdsrutiner for filtreringssystem",
      author: "Johan Olsen",
      date: "10. jan 2026",
      category: "Vedlikehold",
      wordCount: "2,134 ord",
      content: {
        title: "Vedlikeholdsrutiner for filtreringssystem",
        sections: [
          {
            heading: "1. Beskrivelse av system",
            content: "Filtreringssystemet består av tre hovedenheter som prosesserer 500m³/time. Regelmessig vedlikehold er kritisk for optimal drift."
          },
          {
            heading: "2. Daglige rutiner",
            content: "Daglig inspeksjon inkluderer visuell kontroll av trykkfall, lekkasjer, og unormal støy. Verdier skal logges i driftsjournalen."
          },
          {
            heading: "3. Ukentlige rutiner",
            content: "Ukentlig rengjøring av forfiltre og kontroll av slitedeler. Reservedeler skal alltid være tilgjengelig på lager."
          },
          {
            heading: "4. Månedlige rutiner",
            content: "Fullstendig inspeksjon og kalibrering av sensorer. Service av pumper og motorenheter i henhold til leverandørens anbefalinger."
          },
        ],
        references: [
          "Leverandørmanual - FilterTech 3000",
          "Internkontrollforskriften",
          "Vedlikeholdsplan 2026"
        ]
      }
    },
    "5": {
      title: "Miljørapport Q1 2026",
      author: "Anne Berg",
      date: "9. jan 2026",
      category: "Miljø",
      wordCount: "4,231 ord",
      content: {
        title: "Miljørapport Q1 2026",
        sections: [
          {
            heading: "1. Sammendrag",
            content: "Miljørapporten for Q1 2026 viser positive resultater med reduserte utslipp og forbedret avfallshåndtering sammenlignet med samme periode i fjor."
          },
          {
            heading: "2. Utslipp til luft",
            content: "SO2-utslipp er redusert med 12% gjennom implementering av nye skrubbere. NOx-utslipp holder seg stabile og godt under grenseverdier."
          },
          {
            heading: "3. Avfallshåndtering",
            content: "Andel avfall til gjenvinning har økt til 78%. Farlig avfall håndteres i henhold til gjeldende forskrifter."
          },
          {
            heading: "4. Forbedringstiltak",
            content: "Planlagt installasjon av nye filtre i Q2 2026 forventes å redusere støvutslipp med ytterligere 15%."
          },
        ],
        references: [
          "Miljølovgivning Norge",
          "Utslippstillatelse 2025-2030",
          "ISO 14001 - Miljøstyring"
        ]
      }
    },
    "6": {
      title: "HMS-prosedyre 2026-01",
      author: "Sikkerhet Team",
      date: "8. jan 2026",
      category: "Sikkerhet",
      wordCount: "1,923 ord",
      content: {
        title: "HMS-prosedyre 2026-01: Arbeidsområdesikring",
        sections: [
          {
            heading: "1. Formål",
            content: "Denne prosedyren beskriver krav til sikring av arbeidsområder ved Glencore Nikkelverk AS for å forebygge ulykker og sikre trygg gjennomføring av arbeidsoppgaver."
          },
          {
            heading: "2. Ansvar",
            content: "Driftsleder har overordnet ansvar for at arbeidsområder sikres i henhold til denne prosedyren. Alle ansatte har plikt til å følge HMS-krav."
          },
          {
            heading: "3. Sikringskrav",
            content: "Arbeidsområdet må være tydelig merket med barrierer og skilting. Adgang skal være begrenset til autorisert personell med gjeldende arbeidstillatelse."
          },
        ],
        references: [
          "Internkontrollforskriften",
          "Glencore Sikkerhetshåndbok",
          "Arbeidsmiljøloven §4-5"
        ]
      }
    },
    "7": {
      title: "Prosessoptimalisering Q4 2025",
      author: "Teknikk Team",
      date: "7. jan 2026",
      category: "Prosesser",
      wordCount: "2,567 ord",
      content: {
        title: "Prosessoptimalisering Q4 2025",
        sections: [
          {
            heading: "1. Sammendrag",
            content: "Prosessoptimaliseringsprosjektet i Q4 2025 har resultert i betydelige forbedringer i energieffektivitet og produksjonskvalitet."
          },
          {
            heading: "2. Energibesparelser",
            content: "Implementering av nye kontrollalgoritmer har redusert energiforbruk med 8% sammenlignet med Q3 2025."
          },
          {
            heading: "3. Kvalitetsforbedringer",
            content: "Produktrenhetsgrad har økt fra 99.94% til 99.97% gjennom optimalisert temperaturkontroll og prosessjustering."
          },
        ],
        references: [
          "Prosessdata Q3-Q4 2025",
          "Energirapport 2025",
          "ISO 9001:2015"
        ]
      }
    },
  };

  const doc = id ? documents[id] : null;

  if (!doc) {
    return (
      <div className="flex h-screen bg-white">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <FileText className="w-16 h-16 text-[#000000]/20 mx-auto mb-4" />
            <h2 className="text-xl text-[#000000] font-semibold mb-2">Dokument ikke funnet</h2>
            <p className="text-sm text-[#000000] mb-6">Dokumentet du leter etter eksisterer ikke.</p>
            <button
              onClick={() => navigate("/knowledge-bank")}
              className="px-6 py-2 bg-[#00AFAA] hover:bg-[#00AFAA]/90 text-white rounded-md transition-colors text-sm font-semibold"
            >
              Tilbake til kunnskapsbanken
            </button>
          </div>
        </div>
      </div>
    );
  }

  const handleDownload = () => {
    alert(`Last ned: ${doc.title}.pdf`);
  };

  return (
    <div className="flex h-screen bg-white">
      <Sidebar />
      
      <div className="flex-1 flex flex-col overflow-hidden bg-[#00afaa1a]">
        <header className="flex items-center justify-between h-[103px] px-6 bg-[#ededed] border border-[#ededed] flex-shrink-0 mx-6">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate("/knowledge-bank")}
              className="p-2 hover:bg-[#000000]/5 rounded-md transition-colors"
            >
              <ArrowLeft className="w-5 h-5 text-[#000000]" />
            </button>
            <h1 className="text-2xl text-[#000000] font-semibold">Dokumentdetaljer</h1>
          </div>
          <button className="flex items-center gap-2 px-4 py-2 bg-[#00AFAA] hover:bg-[#00AFAA]/90 text-white rounded-md transition-colors text-sm font-semibold">
            <Download className="w-4 h-4" />
            Last ned PDF
          </button>
        </header>

        <div className="flex-1 overflow-auto px-6 pb-4">
          <div className="flex flex-col gap-4 pt-4">
            <div className="bg-white border border-white">
              <div className="p-6 max-w-5xl mx-auto">
                <div className="mb-8 pb-6 border-b border-[#000000]/10">
                  <h1 className="text-2xl text-[#000000] font-semibold mb-4">{doc.content.title}</h1>
                  
                  <div className="flex flex-wrap items-center gap-4 text-sm text-[#000000] mb-4">
                    <div className="flex items-center gap-2">
                      <User className="w-4 h-4" />
                      <span>{doc.author}</span>
                    </div>
                    <span>•</span>
                    <div className="flex items-center gap-2">
                      <Calendar className="w-4 h-4" />
                      <span>{doc.date}</span>
                    </div>
                    <span>•</span>
                    <div className="flex items-center gap-2">
                      <Eye className="w-4 h-4" />
                      <span>{doc.wordCount}</span>
                    </div>
                  </div>

                  <div>
                    <span className="inline-block px-3 py-1 bg-[#00AFAA]/10 text-[#00AFAA] text-xs rounded font-semibold">
                      {doc.category}
                    </span>
                  </div>
                </div>

                {/* Document Content */}
                <div className="space-y-8 mb-8">
                  {doc.content.sections.map((section, index) => (
                    <div key={index}>
                      <h2 className="text-xl text-[#000000] font-semibold mb-3">{section.heading}</h2>
                      <p className="text-[#000000] leading-relaxed">{section.content}</p>
                    </div>
                  ))}
                </div>

                {/* References */}
                <div className="pt-6 border-t border-[#000000]/10 mb-8">
                  <h2 className="text-xl text-[#000000] font-semibold mb-4">Referanser</h2>
                  <ul className="space-y-2">
                    {doc.content.references.map((ref, index) => (
                      <li key={index} className="text-[#000000] leading-relaxed">
                        • {ref}
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Download Button - AT BOTTOM */}
                <div className="flex justify-start">
                  <button
                    onClick={handleDownload}
                    className="flex items-center gap-2 px-8 py-3 bg-[#00AFAA] hover:bg-[#00AFAA]/90 text-white rounded-md transition-colors text-sm font-semibold"
                  >
                    <Download className="w-5 h-5" />
                    Last ned dokument
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}