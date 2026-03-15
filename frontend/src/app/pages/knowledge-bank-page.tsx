import { useState } from "react";
import { Sidebar } from "@/app/components/sidebar";
import { Send, Sparkles, FileText, ExternalLink, User, Plus, MessageSquare, Filter } from "lucide-react";

interface Source {
  id: string;
  title: string;
  author: string;
  date: string;
  category: string;
}

interface ChatMessage {
  role: "user" | "bot";
  message: string;
  timestamp: string;
  sources?: Source[];
}

interface ChatSession {
  id: string;
  title: string;
  timestamp: string;
  messages: ChatMessage[];
  category: string;
}

export function KnowledgeBankPage() {
  const [chatMessage, setChatMessage] = useState("");
  const [selectedDocument, setSelectedDocument] = useState<Source | null>(null);
  const [selectedCategory, setSelectedCategory] = useState("All");
  const [currentSessionId, setCurrentSessionId] = useState("1");
  
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([
    {
      id: "1",
      title: "Ny samtale",
      timestamp: new Date().toISOString(),
      category: "All",
      messages: [
        {
          role: "bot",
          message: "Hei! Jeg er KI-assistenten for Glencore Nikkelverk. Jeg kan hjelpe deg med å analysere dokumenter, svare på spørsmål om prosesser, og foreslå oppdateringer til kunnskapsbanken. Hva kan jeg hjelpe deg med i dag?",
          timestamp: new Date().toISOString(),
        },
      ],
    },
  ]);

  const currentSession = chatSessions.find(s => s.id === currentSessionId);
  const chatHistory = currentSession?.messages || [];

  const categories = ["All", "Sikkerhet", "Vedlikehold", "Prosesser", "Miljø", "Kvalitet"];

  const allDocuments: Source[] = [
    {
      id: "1",
      title: "Prosedyre for elektrolyse-vedlikehold",
      author: "Erik Berg",
      date: "15. jan 2026",
      category: "Vedlikehold",
    },
    {
      id: "2",
      title: "Sikkerhetsprosedyrer smelteverk",
      author: "System",
      date: "12. jan 2026",
      category: "Sikkerhet",
    },
    {
      id: "3",
      title: "Kvalitetskontroll raffinering Q4 2025",
      author: "Maria Hansen",
      date: "11. jan 2026",
      category: "Prosesser",
    },
    {
      id: "4",
      title: "Vedlikeholdsrutiner for filtreringssystem",
      author: "Johan Olsen",
      date: "10. jan 2026",
      category: "Vedlikehold",
    },
    {
      id: "5",
      title: "Miljørapport Q1 2026",
      author: "Anne Berg",
      date: "9. jan 2026",
      category: "Miljø",
    },
    {
      id: "6",
      title: "HMS-prosedyre 2026-01",
      author: "Sikkerhet Team",
      date: "8. jan 2026",
      category: "Sikkerhet",
    },
    {
      id: "7",
      title: "Prosessoptimalisering Q4 2025",
      author: "Teknikk Team",
      date: "7. jan 2026",
      category: "Prosesser",
    },
  ];

  const getFilteredDocuments = () => {
    if (selectedCategory === "All") return allDocuments;
    return allDocuments.filter(doc => doc.category === selectedCategory);
  };

  const handleNewChat = () => {
    const newSession: ChatSession = {
      id: Date.now().toString(),
      title: "Ny samtale",
      timestamp: new Date().toISOString(),
      category: selectedCategory,
      messages: [
        {
          role: "bot",
          message: `Hei! Jeg er KI-assistenten for Glencore Nikkelverk${selectedCategory !== "All" ? ` (kategori: ${selectedCategory})` : ""}. Hva kan jeg hjelpe deg med i dag?`,
          timestamp: new Date().toISOString(),
        },
      ],
    };
    setChatSessions(prev => [newSession, ...prev]);
    setCurrentSessionId(newSession.id);
  };

  const handleSelectSession = (sessionId: string) => {
    setCurrentSessionId(sessionId);
    const session = chatSessions.find(s => s.id === sessionId);
    if (session) {
      setSelectedCategory(session.category);
    }
  };

  const handleCategoryChange = (category: string) => {
    setSelectedCategory(category);
    // Update current session category
    setChatSessions(prev => prev.map(session => 
      session.id === currentSessionId 
        ? { ...session, category } 
        : session
    ));
  };

  const handleSendMessage = () => {
    if (!chatMessage.trim()) return;

    const userMessage = chatMessage;
    setChatMessage("");

    const newUserMessage: ChatMessage = {
      role: "user",
      message: userMessage,
      timestamp: new Date().toISOString(),
    };

    // Update current session with user message
    setChatSessions(prev => prev.map(session => {
      if (session.id === currentSessionId) {
        const updatedMessages = [...session.messages, newUserMessage];
        // Update title based on first user message
        const newTitle = session.messages.length === 1 
          ? userMessage.slice(0, 40) + (userMessage.length > 40 ? "..." : "")
          : session.title;
        return { ...session, messages: updatedMessages, title: newTitle };
      }
      return session;
    }));

    // Simulate AI response with category-filtered sources
    setTimeout(() => {
      const filteredDocs = getFilteredDocuments();
      
      const responses = [
        {
          message: selectedCategory === "All" || selectedCategory === "Vedlikehold" 
            ? "Ifølge prosedyren for elektrolyse-vedlikehold skal temperaturen holdes mellom 1250-1350°C under normal drift. Dette er kritisk for å opprettholde optimal effektivitet og sikkerhet. Prosedyren anbefaler også daglige kontroller av elektrodene og månedlige inspeksjoner av kjølesystemet."
            : "Basert på dokumentene i denne kategorien, kan jeg hjelpe deg med spesifikk informasjon. Vennligst still et mer detaljert spørsmål.",
          sources: filteredDocs.slice(0, 2),
        },
        {
          message: selectedCategory === "All" || selectedCategory === "Sikkerhet"
            ? "Basert på sikkerhetsprosedyrene for smelteverket, må all personell bruke fullt verneutstyr inkludert: hjelm, vernebriller, hørselvern, vernehansker og ildfast arbeidstøy. Før oppstart av smelteovn skal det alltid gjennomføres en sikkerhetsbriefing med alle involverte."
            : "Basert på dokumentene i denne kategorien, kan jeg hjelpe deg med spesifikk informasjon. Vennligst still et mer detaljert spørsmål.",
          sources: filteredDocs.slice(0, 2),
        },
        {
          message: selectedCategory === "All" || selectedCategory === "Prosesser"
            ? "Kvalitetskontrollrapporten for Q4 2025 viser en forbedring på 8.3% i produktrenheten sammenlignet med Q3. De viktigste faktorene som bidro til denne forbedringen var: optimalisert filtreringsprosess, bedre råvarekvalitet, og implementering av nye kvalitetskontrollrutiner."
            : "Basert på dokumentene i denne kategorien, kan jeg hjelpe deg med spesifikk informasjon. Vennligst still et mer detaljert spørsmål.",
          sources: filteredDocs.slice(0, 2),
        },
      ];

      const randomResponse = responses[Math.floor(Math.random() * responses.length)];

      const aiMessage: ChatMessage = {
        role: "bot",
        message: randomResponse.message,
        timestamp: new Date().toISOString(),
        sources: randomResponse.sources,
      };

      setChatSessions(prev => prev.map(session => 
        session.id === currentSessionId 
          ? { ...session, messages: [...session.messages, aiMessage] }
          : session
      ));
    }, 1000);
  };

  return (
    <div className="flex h-screen bg-white">
      <Sidebar />

      <div className="flex-1 flex flex-col overflow-hidden bg-[#00afaa1a]">
        <header className="flex items-center justify-between h-[103px] px-6 bg-[#ededed] border border-[#ededed] flex-shrink-0 mx-6">
          <h1 className="text-2xl text-[#000000] font-semibold">Kunnskapsbank</h1>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-[#000000]/60" />
              <span className="text-sm text-[#000000]/60 font-semibold">Kategori:</span>
            </div>
            <select
              value={selectedCategory}
              onChange={(e) => handleCategoryChange(e.target.value)}
              className="px-4 py-2 bg-white border border-[#000000]/20 rounded-lg text-sm font-semibold text-[#000000] focus:outline-none focus:ring-2 focus:ring-[#00AFAA] focus:border-transparent"
            >
              {categories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>
        </header>

        <div className="flex-1 overflow-hidden px-6 pb-4">
          <div className="flex flex-col gap-4 pt-4 h-full">
            <div className="bg-white border border-white flex-1 flex overflow-hidden">
              <div className="w-[320px] bg-white flex flex-col overflow-hidden border-r-2 border-[#00AFAA]">
                 <div className="p-4 border-b border-[#000000]/10">
                  <button
                    onClick={handleNewChat}
                    className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-[#00AFAA] hover:bg-[#00AFAA]/90 text-white rounded-lg transition-colors text-sm font-semibold"
                  >
                    <Plus className="w-4 h-4" />
                    Ny samtale
                  </button>
                </div>

                 <div className="flex-1 overflow-y-auto p-4 space-y-2">
                  <p className="text-xs font-semibold text-[#000000]/60 mb-3 px-2">SAMTALEHISTORIKK</p>
                  {chatSessions.map((session) => (
                    <button
                      key={session.id}
                      onClick={() => handleSelectSession(session.id)}
                      className={`w-full text-left px-3 py-3 rounded-lg transition-colors ${
                        currentSessionId === session.id
                          ? "bg-[#00AFAA]/10 border border-[#00AFAA]"
                          : "bg-[#F5F5F5] hover:bg-[#EDEDED] border border-transparent"
                      }`}
                    >
                      <div className="flex items-start gap-2 mb-2">
                        <MessageSquare className={`w-4 h-4 flex-shrink-0 mt-0.5 ${
                          currentSessionId === session.id ? "text-[#00AFAA]" : "text-[#000000]/40"
                        }`} />
                        <p className="text-sm text-[#000000] line-clamp-2 font-medium">
                          {session.title}
                        </p>
                      </div>
                      <div className="flex items-center justify-between">
                        <p className="text-xs text-[#000000]/60">
                          {new Date(session.timestamp).toLocaleDateString("nb-NO", {
                            day: "numeric",
                            month: "short",
                          })}
                        </p>
                        {session.category !== "All" && (
                          <span className="text-xs px-2 py-0.5 bg-[#00AFAA]/20 text-[#00AFAA] rounded font-semibold">
                            {session.category}
                          </span>
                        )}
                      </div>
                    </button>
                  ))}
                </div>
              </div>

               <div className="flex-1 bg-white flex flex-col overflow-hidden">
                {selectedCategory !== "All" && (
                  <div className="px-8 py-3 bg-[#00AFAA]/5 border-b border-[#00AFAA]/20">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-[#000000]/60">Søker kun i kategori:</span>
                      <span className="px-3 py-1 bg-[#00AFAA] text-white text-xs rounded-full font-semibold">
                        {selectedCategory}
                      </span>
                      <span className="text-xs text-[#000000]/60">
                        ({getFilteredDocuments().length} dokumenter)
                      </span>
                    </div>
                  </div>
                )}

                <div className="flex-1 overflow-y-auto p-8 space-y-6">
                  {chatHistory.map((msg, index) => (
                    <div key={index}>
                      {msg.role === "user" ? (
                        <div className="flex justify-end">
                          <div className="max-w-[70%]">
                            <div className="flex items-start gap-3 justify-end mb-2">
                              <div className="text-right">
                                <p className="text-xs font-semibold text-[#000000]/60 mb-1">Du</p>
                              </div>
                              <div className="w-8 h-8 bg-[#00AFAA] rounded-lg flex items-center justify-center flex-shrink-0">
                                <User className="w-4 h-4 text-white" />
                              </div>
                            </div>
                            <div className="bg-[#00AFAA] rounded-2xl rounded-tr-sm p-4">
                              <p className="text-base text-white leading-relaxed">
                                {msg.message}
                              </p>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="max-w-[85%]">
                          <div className="flex items-start gap-3 mb-2">
                            <div className="w-8 h-8 bg-[#00AFAA] rounded-lg flex items-center justify-center flex-shrink-0">
                              <Sparkles className="w-4 h-4 text-white" />
                            </div>
                            <div>
                              <p className="text-xs font-semibold text-[#000000]/60">KI Assistent</p>
                            </div>
                          </div>
                          <div className="ml-11">
                            <div className="bg-[#F5F5F5] rounded-2xl rounded-tl-sm p-5 mb-4">
                              <p className="text-base text-[#000000] leading-relaxed">
                                {msg.message}
                              </p>
                            </div>

                            {msg.sources && msg.sources.length > 0 && (
                              <div className="space-y-2">
                                <p className="text-xs text-[#000000]/60 font-semibold mb-3">
                                  Kilder ({msg.sources.length})
                                </p>
                                {msg.sources.map((source) => (
                                  <div
                                    key={source.id}
                                    className="bg-white border border-[#000000]/10 rounded-lg p-4 hover:border-[#00AFAA] hover:shadow-sm transition-all cursor-pointer"
                                  >
                                    <div className="flex items-start gap-3">
                                      <div className="w-10 h-10 bg-[#00AFAA]/10 rounded-md flex items-center justify-center flex-shrink-0">
                                        <FileText className="w-5 h-5 text-[#00AFAA]" />
                                      </div>
                                      <div className="flex-1 min-w-0">
                                        <h4 className="text-sm text-[#000000] font-semibold mb-1">
                                          {source.title}
                                        </h4>
                                        <div className="flex items-center gap-2 text-xs text-[#000000] font-semibold">
                                          <span>{source.author}</span>
                                          <span>•</span>
                                          <span>{source.date}</span>
                                          <span>•</span>
                                          <span className="text-[#00AFAA]">
                                            {source.category}
                                          </span>
                                        </div>
                                      </div>
                                      <button
                                        onClick={() => setSelectedDocument(source)}
                                        className="flex items-center gap-1 px-3 py-1.5 bg-[#00AFAA]/10 hover:bg-[#00AFAA]/20 text-[#00AFAA] rounded-md transition-colors text-xs font-semibold"
                                      >
                                        Vis hele dokumentet
                                        <ExternalLink className="w-3 h-3" />
                                      </button>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                <div className="border-t border-[#000000]/10 p-6 bg-white">
                  <div className="flex gap-3">
                    <input
                      type="text"
                      placeholder="Still et spørsmål til kunnskapsbanken..."
                      value={chatMessage}
                      onChange={(e) => setChatMessage(e.target.value)}
                      onKeyPress={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          handleSendMessage();
                        }
                      }}
                      className="flex-1 px-5 py-3 bg-[#F5F5F5] border-0 rounded-lg focus:ring-2 focus:ring-[#00AFAA] outline-none text-base text-[#000000] placeholder:text-[#000000]/40"
                    />
                    <button
                      onClick={handleSendMessage}
                      disabled={!chatMessage.trim()}
                      className="px-5 py-3 bg-[#00AFAA] hover:bg-[#00AFAA]/90 disabled:bg-[#00AFAA]/50 disabled:cursor-not-allowed text-white rounded-lg transition-colors font-semibold"
                    >
                      <Send className="w-5 h-5" />
                    </button>
                  </div>
                  <p className="text-xs text-[#000000]/40 text-center mt-3">
                    KI kan gjøre feil. Sjekk viktig informasjon.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Document Viewer Modal */}
      {selectedDocument && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-8 z-50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-4xl h-[90vh] flex flex-col">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-[#000000]/10 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-[#00AFAA]/10 rounded-lg flex items-center justify-center">
                  <FileText className="w-5 h-5 text-[#00AFAA]" />
                </div>
                <div>
                  <h2 className="text-lg text-[#000000] font-semibold">
                    {selectedDocument.title}
                  </h2>
                  <p className="text-xs text-[#000000]/60">
                    {selectedDocument.author} • {selectedDocument.date}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setSelectedDocument(null)}
                className="px-4 py-2 bg-[#F5F5F5] hover:bg-[#E7E7E7] text-[#000000] rounded-lg transition-colors text-sm font-semibold"
              >
                Lukk
              </button>
            </div>

            {/* Modal Content */}
            <div className="flex-1 overflow-y-auto p-8">
              <div className="prose max-w-none">
                <div className="bg-[#E6F7F7] border-l-4 border-[#00AFAA] p-4 rounded-r-lg mb-6">
                  <p className="text-sm text-[#000000]">
                    <span className="font-semibold">Kategori:</span> {selectedDocument.category}
                  </p>
                </div>

                <h3 className="text-xl text-[#000000] font-semibold mb-4">Dokumentinnhold</h3>
                
                <p className="text-base text-[#000000] leading-relaxed mb-4">
                  Dette er et eksempeldokument fra Glencore Nikkelverk kunnskapsbank. 
                  I en produksjonsapplikasjon ville det fulle dokumentinnholdet blitt vist her, 
                  inkludert all teknisk informasjon, prosedyrer, og relevante data.
                </p>

                <h4 className="text-lg text-[#000000] font-semibold mb-3 mt-6">Hovedpunkter:</h4>
                <ul className="space-y-2 mb-6">
                  <li className="text-base text-[#000000]">Detaljerte sikkerhetsprosedyrer og retningslinjer</li>
                  <li className="text-base text-[#000000]">Tekniske spesifikasjoner og parametere</li>
                  <li className="text-base text-[#000000]">Vedlikeholdsrutiner og tidsplaner</li>
                  <li className="text-base text-[#000000]">Kvalitetskontrollkriterier</li>
                  <li className="text-base text-[#000000]">Relevante referanser til andre dokumenter</li>
                </ul>

                <h4 className="text-lg text-[#000000] font-semibold mb-3">Relatert informasjon:</h4>
                <p className="text-base text-[#000000] leading-relaxed">
                  Dette dokumentet er en del av Glencore Nikkelverks omfattende kunnskapsbank 
                  som inneholder operative prosedyrer, sikkerhetsinformasjon, og teknisk dokumentasjon 
                  for alle aspekter av produksjonsanlegget.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}