import { useState } from "react";
import { Sidebar } from "@/app/components/sidebar";
import { MessageSquare, FileText, Clock, ChevronRight, X, Send, XCircle, Trash2 } from "lucide-react";
import { useDocuments } from "@/app/context/documents-context";
import { useToast } from "@/app/context/toast-context";
import { getAuthPermissionErrorMessage } from "@/utils/auth-errors";

interface ChatMessage {
  role: "user" | "ai";
  content: string;
}

export function QueuePage() {
  const { getPendingDocuments, getRejectedDocuments, approveDocument, rejectDocument, deleteDocument } = useDocuments();
  const { showToast } = useToast();
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [revisedContent, setRevisedContent] = useState("");
  const [viewRejectedDoc, setViewRejectedDoc] = useState<string | null>(null);
  const [viewingOriginal, setViewingOriginal] = useState(false);

  const documents = getPendingDocuments();
  const rejectedDocuments = getRejectedDocuments();
  const selectedDocument = documents.find(doc => doc.id === selectedDocId);
  const viewedRejectedDocument = rejectedDocuments.find(doc => doc.id === viewRejectedDoc);

  const handleDocumentSelect = (docId: string) => {
    const doc = documents.find(d => d.id === docId);
    setSelectedDocId(docId);
    setRevisedContent(doc?.revisedContent || "");
    setChatMessages([]);
    setViewingOriginal(false);
  };

  const handleApprove = async () => {
    if (selectedDocId) {
      try {
        await approveDocument(selectedDocId);
        showToast("Dokument godkjent. AI-revidert versjon er lagret i kunnskapsbanken.", "success");
        setSelectedDocId(null);
        setChatMessages([]);
        setRevisedContent("");
      } catch (error) {
        console.error("Failed to approve document:", error);
        showToast(`Feil ved godkjenning av dokument. ${getAuthPermissionErrorMessage(error)}`, "error");
      }
    }
  };

  const handleReject = async () => {
    if (selectedDocId) {
      try {
        await rejectDocument(selectedDocId);
        showToast("Dokument avvist. Dokumentet er ikke publisert i kunnskapsbanken.", "success");
        setSelectedDocId(null);
        setChatMessages([]);
        setRevisedContent("");
      } catch (error) {
        console.error("Failed to reject document:", error);
        showToast(`Feil ved avvisning av dokument. ${getAuthPermissionErrorMessage(error)}`, "error");
      }
    }
  };

  const closeModal = () => {
    setSelectedDocId(null);
    setChatMessages([]);
    setRevisedContent("");
  };

  const handleDeleteRejected = async (docId: string) => {
    const doc = rejectedDocuments.find(d => d.id === docId);
    if (window.confirm(`Er du sikker på at du vil slette "${doc?.title}"?\n\nDenne handlingen kan ikke angres.`)) {
      try {
        await deleteDocument(docId);
        setViewRejectedDoc(null);
        showToast("Dokument slettet. Dokumentet er permanent fjernet fra systemet.", "success");
      } catch (error) {
        console.error("Failed to delete document:", error);
        showToast(`Feil ved sletting av dokument. ${getAuthPermissionErrorMessage(error)}`, "error");
      }
    }
  };

  const handleSendMessage = () => {
    if (!inputMessage.trim()) return;

    const userMessage: ChatMessage = {
      role: "user",
      content: inputMessage,
    };

    setChatMessages(prev => [...prev, userMessage]);

    // Simulate AI response
    setTimeout(() => {
      const aiResponse: ChatMessage = {
        role: "ai",
        content: getAIResponse(inputMessage),
      };
      setChatMessages(prev => [...prev, aiResponse]);

      // Update revised content based on the request
      if (inputMessage.toLowerCase().includes("temperatur")) {
        setRevisedContent(prev => prev.replace("1250-1350°C", "1300-1400°C"));
      } else if (inputMessage.toLowerCase().includes("intervall")) {
        setRevisedContent(prev => prev.replace("hver 4. måned", "hver 3. måned"));
      } else if (inputMessage.toLowerCase().includes("sikkerhet")) {
        setRevisedContent(prev => prev + "\n\n9. Ekstra Sikkerhetstiltak\n\nVed høyrisiko-operasjoner skal det alltid være minimum to personer til stede. Alle ansatte må ha fullført HMS-opplæring nivå 2.");
      }
    }, 1000);

    setInputMessage("");
  };

  const getAIResponse = (message: string): string => {
    const lowerMessage = message.toLowerCase();

    if (lowerMessage.includes("temperatur")) {
      return "Jeg har oppdatert temperaturverdiene til 1300-1400°C basert på de nyeste prosessdataene fra Q1 2026. Dette gir bedre energieffektivitet og produktkvalitet.";
    } else if (lowerMessage.includes("intervall")) {
      return "Jeg har endret vedlikeholdsintervallet til hver 3. måned. Dette er i tråd med anbefalinger fra utstyrsprodusentene og vil redusere risikoen for uventede stopp.";
    } else if (lowerMessage.includes("sikkerhet")) {
      return "Jeg har lagt til et nytt avsnitt om ekstra sikkerhetstiltak for høyrisiko-operasjoner. Dette inkluderer krav om minimum to personer og HMS-opplæring nivå 2.";
    } else if (lowerMessage.includes("forkort") || lowerMessage.includes("kortere")) {
      return "Jeg kan forkorte dokumentet ved å fjerne unødvendige detaljer og fokusere på de viktigste punktene. Skal jeg gjøre det?";
    } else if (lowerMessage.includes("utvid") || lowerMessage.includes("mer detalj")) {
      return "Jeg kan utvide dokumentet med mer detaljert informasjon om prosedyrene, inkludert trinn-for-trinn instruksjoner og illustrasjoner. Ønsker du det?";
    } else {
      return "Jeg forstår din forespørsel. Jeg kan hjelpe deg med å:\n• Endre temperaturverdier\n• Justere vedlikeholdsintervaller\n• Legge til sikkerhetsprosedyrer\n• Forkorte eller utvide innholdet\n\nHva ønsker du at jeg skal fokusere på?";
    }
  };

  return (
    <div className="flex h-screen bg-white">
      <Sidebar />
      
      <div className="flex-1 flex flex-col overflow-hidden bg-[#00afaa1a]">
        <header className="flex items-center h-[103px] px-6 bg-[#ededed] border border-[#ededed] flex-shrink-0 mx-6">
          <h1 className="text-2xl text-[#000000] font-semibold">Til godkjenning</h1>
        </header>

        <div className="flex-1 overflow-auto px-6 pb-4">
          <div className="flex flex-col gap-4 pt-4">
            <div className="bg-white border border-white">
              <div className="p-6">
                {/* Header with Stats */}
                <div className="flex items-start justify-between mb-6">
                  <div>
                    <h2 className="text-xl text-[#000000] font-semibold mb-2">Velg et forslag</h2>
                    <p className="text-sm text-[#000000]">
                      Klikk på et forslag til venstre for å se detaljer og godkjenne.
                    </p>
                  </div>
                  
                  <div className="bg-white border border-[#000000]/10 rounded-lg p-4 min-w-[180px]">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-[#000000] mb-1">Venter godkjenning</p>
                        <p className="text-4xl text-[#000000] font-light leading-none">{documents.length}</p>
                      </div>
                      <div className="w-10 h-10 bg-[#82131E]/10 rounded-full flex items-center justify-center flex-shrink-0">
                        <Clock className="w-5 h-5 text-[#82131E]" />
                      </div>
                    </div>
                  </div>
                </div>
 
                <div className="bg-white border border-[#000000]/10 rounded-lg p-6 mb-8">
                  <h3 className="text-base text-[#000000] font-semibold mb-1">Forslag til godkjenning</h3>
                  <p className="text-sm text-[#000000] mb-6">Gjennomgå og godkjenn KI-foreslåtte oppdateringer</p>
                  
                  <div className="space-y-4">
                    {documents.map((doc) => (
                      <div
                        key={doc.id}
                        className="border border-[#000000]/10 rounded-lg p-6 hover:bg-[#F5F5F5] transition-colors cursor-pointer flex items-center gap-4 group"
                        onClick={() => handleDocumentSelect(doc.id)}
                      >
                        <div className="flex-shrink-0">
                          <div className="w-12 h-12 rounded-lg bg-[#00AFAA]/10 flex items-center justify-center">
                            <FileText className="w-6 h-6 text-[#00AFAA]" />
                          </div>
                         </div>
 
                        <div className="flex-1 min-w-0">
                          <h4 className="text-base text-[#000000] mb-2 font-normal">{doc.title}</h4>
                          <div className="mb-2">
                            <span className="inline-block px-2 py-0.5 bg-[#000000]/5 rounded text-xs font-semibold text-[#000000]">
                              {doc.category}
                            </span>
                            {doc.isProcessing && (
                              <span className="inline-block ml-2 px-2 py-0.5 bg-[#00AFAA]/10 rounded text-xs font-semibold text-[#007b77]">
                                AI behandler...
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-[#000000]">
                            Lastet opp av {doc.uploadedBy} · {doc.uploadedAt}
                           </p>
                        </div>
 
                        <ChevronRight className="w-5 h-5 text-[#000000]/30 flex-shrink-0" />
                      </div>
                    ))}
                   </div>
                </div>
 
                {rejectedDocuments.length > 0 && (
                  <div className="bg-white border border-[#82131E]/20 rounded-lg p-6">
                    <div className="flex items-center gap-2 mb-1">
                      <XCircle className="w-5 h-5 text-[#82131E]" />
                      <h3 className="text-lg text-[#000000] font-semibold">Avviste dokumenter</h3>
                    </div>
                    <p className="text-sm text-[#000000] mb-6">Dokumenter som ikke ble godkjent</p>
                    
                    <div className="space-y-4">
                      {rejectedDocuments.map((doc) => (
                        <div
                          key={doc.id}
                          className="border border-[#82131E]/20 bg-[#82131E]/5 rounded-lg p-6 hover:bg-[#82131E]/10 transition-colors cursor-pointer flex items-center gap-4 group"
                           onClick={() => setViewRejectedDoc(doc.id)}
                        >
                          <div className="flex-shrink-0">
                            <div className="w-12 h-12 rounded-lg bg-[#82131E]/10 flex items-center justify-center">
                              <FileText className="w-6 h-6 text-[#82131E]" />
                             </div>
                           </div>
 
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-2">
                              <h4 className="text-base text-[#000000] font-normal">{doc.title}</h4>
                              <span className="inline-flex items-center px-2 py-0.5 bg-[#82131E] text-white rounded text-xs font-semibold">
                                AVVIST
                              </span>
                            </div>
                            <div className="mb-2">
                              <span className="inline-block px-2 py-0.5 bg-[#000000]/5 rounded text-xs font-semibold text-[#000000]">
                                {doc.category}
                              </span>
                            </div>
                            <p className="text-sm text-[#000000]">
                               Lastet opp av {doc.uploadedBy} · {doc.uploadedAt}
                            </p>
                          </div>
 
                          <ChevronRight className="w-5 h-5 text-[#82131E]/60 flex-shrink-0" />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

       {selectedDocId && selectedDocument && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-8 z-50">
          <div className="bg-white rounded-lg w-[1100px] h-[700px] flex flex-col shadow-2xl">
            <div className="flex items-center justify-between px-6 py-4 border-b border-[#000000]/10 flex-shrink-0">
              <div className="flex items-center gap-4">
                <h2 className="text-lg text-[#000000] font-semibold">
                  {viewingOriginal ? "Original Dokument" : "Gjennomgå AI-forslag"}
                </h2>
                {!viewingOriginal && (
                  <button
                    onClick={() => setViewingOriginal(true)}
                    className="flex items-center gap-2 px-4 py-2 bg-white border border-[#00AFAA] text-[#00AFAA] rounded-md hover:bg-[#E6F7F7] transition-colors text-sm"
                  >
                    <FileText className="w-4 h-4" />
                    Vis original
                  </button>
                )}
                {viewingOriginal && (
                  <button
                    onClick={() => setViewingOriginal(false)}
                    className="flex items-center gap-2 px-4 py-2 bg-white border border-[#00AFAA] text-[#00AFAA] rounded-md hover:bg-[#E6F7F7] transition-colors text-sm"
                  >
                    <FileText className="w-4 h-4" />
                    Tilbake til AI-forslag
                  </button>
                )}
              </div>
              <button
                onClick={() => {
                  closeModal();
                }}
                className="p-2 hover:bg-[#000000]/5 rounded-md transition-colors"
              >
                <X className="w-5 h-5 text-[#000000]" />
              </button>
            </div>

             {viewingOriginal ? (
               <div className="flex-1 overflow-hidden flex flex-col min-h-0">
                 <div className="flex-1 overflow-auto p-8 bg-white">
                  <div className="max-w-4xl mx-auto">
                    <h3 className="text-xl text-[#000000] font-semibold mb-8">{selectedDocument.title}</h3>
                    <div className="text-sm text-[#000000] leading-relaxed whitespace-pre-wrap">
                      {selectedDocument.originalContent}
                    </div>
                   </div>
                </div>
                
                <div className="px-6 py-4 border-t border-[#000000]/10 flex items-center bg-white flex-shrink-0">
                  <p className="text-xs text-[#000000]">
                    Dette er det originale dokumentet før AI-revisjon
                  </p>
                 </div>
              </div>
            ) : (
              <>
                <div className="flex-1 overflow-hidden flex min-h-0">
                  <div className="flex-1 flex flex-col overflow-hidden border-r border-[#00AFAA] min-w-0">
                    <div className="flex-1 flex flex-col overflow-hidden min-h-0">
                      <div className="px-6 py-3 bg-[#E6F7F7] border-b border-[#00AFAA] flex-shrink-0">
                        <h3 className="text-sm text-[#000000] font-semibold">AI-Revidert Forslag</h3>
                        <p className="text-xs text-[#000000] mt-1">Bruk chat til høyre for å justere innholdet</p>
                      </div>
                      <div className="flex-1 overflow-auto p-6 text-sm text-[#000000] leading-relaxed">
                        <div className="whitespace-pre-wrap">{revisedContent}</div>
                      </div>
                     </div>
                  </div>
 
                  <div className="w-[400px] flex flex-col bg-white">
                    <div className="px-6 py-3 bg-[#00AFAA] border-b border-[#00AFAA]">
                      <div className="flex items-center gap-2">
                        <MessageSquare className="w-5 h-5 text-white" />
                        <h3 className="text-sm text-white font-semibold">Samarbeid med AI</h3>
                      </div>
                       <p className="text-xs text-white/90 mt-1">Still spørsmål eller be om endringer</p>
                    </div>
 
                    <div className="flex-1 overflow-auto p-4 bg-[#F5F5F5] space-y-3">
                      {chatMessages.length === 0 && (
                        <div className="p-6 bg-white rounded-lg border border-[#000000]/10 mt-4">
                          <p className="text-sm text-[#000000] leading-relaxed">
                            Hei! Jeg kan hjelpe deg med å justere dokumentet. Jeg kan hjelpe deg med å endre verdier, legge til informasjon, eller forkorte/utvide innholdet.
                          </p>
                          
                          <p className="text-sm text-[#000000] mt-4">
                            Hva ønsker du å endre i dokumentet?
                          </p>
                        </div>
                      )}

                      {chatMessages.map((msg, idx) => (
                        <div
                          key={idx}
                          className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                        >
                          <div
                            className={`max-w-[85%] px-4 py-2.5 rounded-lg text-xs ${
                              msg.role === "user"
                                ? "bg-[#00AFAA] text-white"
                                : "bg-white border border-[#000000]/10 text-[#000000]"
                            }`}
                          >
                            {msg.role === "ai" && (
                              <div className="flex items-center gap-2 mb-1">
                                <MessageSquare className="w-3 h-3 text-[#00AFAA]" />
                                <span className="text-xs font-semibold text-[#00AFAA]">AI-Agent</span>
                              </div>
                            )}
                            <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                          </div>
                        </div>
                       ))}
                    </div>
 
                    <div className="p-4 border-t border-[#000000]/10 bg-white">
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={inputMessage}
                          onChange={(e) => setInputMessage(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
                          placeholder="Skriv en melding..."
                          className="flex-1 px-3 py-2 border border-[#000000]/20 rounded-md text-xs focus:outline-none focus:ring-2 focus:ring-[#00AFAA] focus:border-transparent"
                        />
                        <button
                          onClick={handleSendMessage}
                          disabled={!inputMessage.trim()}
                          className="px-4 py-2 bg-[#00AFAA] hover:bg-[#00AFAA]/90 disabled:bg-[#000000]/10 disabled:cursor-not-allowed text-white rounded-md transition-colors"
                        >
                          <Send className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
               </>
            )}
 
            <div className="px-6 py-4 border-t border-[#000000]/10 flex items-center justify-between bg-white">
               {!viewingOriginal ? (
                 <>
                   <div className="flex items-center gap-2">
                    <div className="w-8 h-8 bg-[#00AFAA]/10 rounded-full flex items-center justify-center">
                      <MessageSquare className="w-4 h-4 text-[#00AFAA]" />
                    </div>
                    <p className="text-xs text-[#000000]">
                      Bruk chatten for å justere dokumentet før godkjenning
                     </p>
                  </div>
 
                  <div className="flex items-center gap-3">
                    <button
                      onClick={handleReject}
                      className="flex items-center gap-2 px-6 py-2.5 bg-white border-2 border-[#82131E] text-[#82131E] rounded-md hover:bg-[#82131E]/5 transition-colors text-sm font-semibold"
                    >
                      <X className="w-4 h-4" />
                      Ikke Godkjent
                    </button>
                    <button
                      onClick={handleApprove}
                      className="flex items-center gap-2 px-6 py-2.5 bg-[#00AFAA] hover:bg-[#00AFAA]/90 text-white rounded-md transition-colors text-sm font-semibold"
                    >
                      <span className="text-lg leading-none">✓</span>
                      Godkjenn AI-versjon
                    </button>
                  </div>
                </>
              ) : null}
            </div>
          </div>
         </div>
      )}
 
      {viewRejectedDoc && viewedRejectedDocument && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-8 z-50">
          <div className="bg-white rounded-lg w-full max-w-3xl max-h-[90vh] flex flex-col shadow-2xl">
            <div className="px-6 py-4 border-b border-[#82131E]/20 bg-[#82131E]/5 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-[#82131E]/10 rounded-lg flex items-center justify-center">
                  <XCircle className="w-5 h-5 text-[#82131E]" />
                </div>
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <h2 className="text-lg text-[#000000] font-semibold">
                      {viewedRejectedDocument.title}
                    </h2>
                    <span className="inline-flex items-center px-2 py-0.5 bg-[#82131E] text-white rounded text-xs font-semibold">
                      AVVIST
                    </span>
                  </div>
                  <p className="text-xs text-[#000000]/60">
                    {viewedRejectedDocument.uploadedBy} · {viewedRejectedDocument.uploadedAt}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setViewRejectedDoc(null)}
                className="px-4 py-2 bg-white hover:bg-[#F5F5F5] text-[#000000] rounded-lg transition-colors text-sm font-semibold border border-[#000000]/10"
              >
                 Lukk
              </button>
            </div>
 
            <div className="flex-1 overflow-y-auto p-8">
              <div className="bg-[#82131E]/5 border-l-4 border-[#82131E] p-4 rounded-r-lg mb-6">
                <p className="text-sm text-[#000000]">
                  <span className="font-semibold">Kategori:</span> {viewedRejectedDocument.category}
                </p>
                <p className="text-xs text-[#000000]/70 mt-2">
                  Dette dokumentet ble avvist og er ikke publisert i kunnskapsbanken.
                </p>
              </div>

              <h3 className="text-lg text-[#000000] font-semibold mb-4">AI-Revidert innhold (avvist)</h3>
              <div className="bg-[#F5F5F5] rounded-lg p-6 mb-6">
                <p className="text-sm text-[#000000] leading-relaxed whitespace-pre-wrap">
                  {viewedRejectedDocument.revisedContent}
                </p>
              </div>

              <h3 className="text-lg text-[#000000] font-semibold mb-4">Original innhold</h3>
              <div className="bg-white border border-[#000000]/10 rounded-lg p-6">
                <p className="text-sm text-[#000000] leading-relaxed whitespace-pre-wrap">
                  {viewedRejectedDocument.originalContent}
                </p>
               </div>
            </div>
 
            <div className="px-6 py-4 border-t border-[#82131E]/20 bg-white flex items-center justify-between">
              <p className="text-xs text-[#000000]/60">
                Dette dokumentet kan slettes permanent fra systemet
              </p>
              <button
                onClick={() => handleDeleteRejected(viewedRejectedDocument.id)}
                className="flex items-center gap-2 px-4 py-2 bg-[#82131E] hover:bg-[#82131E]/90 text-white rounded-lg transition-colors text-sm font-semibold"
              >
                <Trash2 className="w-4 h-4" />
                Slett dokument
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}