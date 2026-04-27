import { useEffect, useMemo, useState } from "react";
import { ExternalLink, FileText, Search } from "lucide-react";

import { Sidebar } from "@/app/components/sidebar";
import { documentService } from "@/services/documentService";
import { getAuthPermissionErrorMessage } from "@/utils/auth-errors";

type KbListItem = {
  kb_path: string;
  title: string;
  author: string;
  date: string;
  category: string;
};

export function FilesPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [docs, setDocs] = useState<KbListItem[]>([]);

  const [selectedDoc, setSelectedDoc] = useState<KbListItem | null>(null);
  const [selectedDocContent, setSelectedDocContent] = useState("");
  const [selectedDocLoading, setSelectedDocLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    void (async () => {
      try {
        const result = await documentService.listKnowledgeBankDocuments({
          limit: 2000,
          offset: 0,
          category: "All",
        });

        if (cancelled) return;
        setDocs((result.documents || []) as KbListItem[]);
      } catch (e) {
        if (cancelled) return;
        setError(`Klarte ikke å hente filer. ${getAuthPermissionErrorMessage(e)}`);
      } finally {
        if (cancelled) return;
        setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedDoc) {
      setSelectedDocContent("");
      setSelectedDocLoading(false);
      return;
    }

    let cancelled = false;
    setSelectedDocLoading(true);

    void (async () => {
      try {
        const doc = await documentService.getKnowledgeBankDocument(selectedDoc.kb_path);
        if (cancelled) return;
        setSelectedDocContent(doc.content || "");
      } catch (e) {
        if (cancelled) return;
        setSelectedDocContent(`Klarte ikke å hente dokumentinnhold. ${getAuthPermissionErrorMessage(e)}`);
      } finally {
        if (cancelled) return;
        setSelectedDocLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [selectedDoc]);

  const filteredDocs = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return docs;

    return docs.filter((d) => {
      return (
        (d.title || "").toLowerCase().includes(q) ||
        (d.author || "").toLowerCase().includes(q) ||
        (d.category || "").toLowerCase().includes(q) ||
        (d.kb_path || "").toLowerCase().includes(q)
      );
    });
  }, [docs, query]);

  return (
    <div className="flex h-screen bg-white">
      <Sidebar />

      <div className="flex-1 flex flex-col overflow-hidden bg-[#00afaa1a]">
        <header className="flex items-center justify-between h-[103px] px-6 bg-[#ededed] border border-[#ededed] flex-shrink-0 mx-6">
          <div>
            <h1 className="text-2xl text-[#000000] font-semibold">Filer</h1>
            <p className="text-xs text-[#000000]/60 mt-1">Lesegodkjente dokumenter fra kunnskapsbanken</p>
          </div>

          <div className="text-sm text-[#000000]/70 font-semibold">
            {loading ? "Laster..." : `${filteredDocs.length} dokumenter`}
          </div>
        </header>

        <div className="flex-1 overflow-hidden px-6 pb-4 pt-4">
          <div className="bg-white border border-white h-full flex flex-col overflow-hidden">
            <div className="px-6 py-4 border-b border-[#000000]/10 flex items-center justify-between gap-4">
              <p className="text-sm text-[#000000]/70">Bla gjennom dokumenter og åpne innhold i lesemodus.</p>
              <div className="relative w-full max-w-md">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[#000000]/40" />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Søk i tittel, kategori eller sti..."
                  className="w-full pl-9 pr-3 py-2 bg-[#F5F5F5] border border-[#000000]/10 rounded-lg text-sm text-[#000000] focus:outline-none focus:ring-2 focus:ring-[#00AFAA]"
                />
              </div>
            </div>

            {error && (
              <div className="px-6 py-4 text-sm text-[#7C0D15] bg-[#FCEBEC] border-b border-[#000000]/10">{error}</div>
            )}

            <div className="flex-1 overflow-y-auto divide-y divide-[#000000]/10">
              {!loading && filteredDocs.length === 0 && !error && (
                <div className="px-6 py-8 text-sm text-[#000000]/60">Ingen dokumenter funnet.</div>
              )}

              {filteredDocs.map((doc) => (
                <div key={doc.kb_path} className="px-6 py-4 flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <p className="text-base text-[#000000] font-semibold truncate">{doc.title || "(uten tittel)"}</p>
                    <p className="text-xs text-[#000000]/60 mt-1 break-all">{doc.kb_path}</p>
                    <div className="flex items-center gap-2 mt-1 text-xs text-[#000000]/70">
                      <span>{doc.author || "Ukjent"}</span>
                      <span>•</span>
                      <span>{doc.date || "Ukjent dato"}</span>
                      <span>•</span>
                      <span className="text-[#00AFAA] font-semibold">{doc.category || "Ukjent kategori"}</span>
                    </div>
                  </div>

                  <button
                    onClick={() => setSelectedDoc(doc)}
                    className="flex items-center gap-2 px-3 py-2 bg-[#00AFAA]/10 hover:bg-[#00AFAA]/20 text-[#00AFAA] rounded-lg transition-colors text-sm font-semibold"
                  >
                    Åpne
                    <ExternalLink className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {selectedDoc && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-8 z-50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-4xl h-[90vh] flex flex-col">
            <div className="px-6 py-4 border-b border-[#000000]/10 flex items-center justify-between">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-10 h-10 bg-[#00AFAA]/10 rounded-lg flex items-center justify-center flex-shrink-0">
                  <FileText className="w-5 h-5 text-[#00AFAA]" />
                </div>
                <div className="min-w-0">
                  <h2 className="text-lg text-[#000000] font-semibold truncate">{selectedDoc.title}</h2>
                  <p className="text-xs text-[#000000]/60 truncate">{selectedDoc.kb_path}</p>
                </div>
              </div>
              <button
                onClick={() => setSelectedDoc(null)}
                className="px-4 py-2 bg-[#F5F5F5] hover:bg-[#E7E7E7] text-[#000000] rounded-lg transition-colors text-sm font-semibold"
              >
                Lukk
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-8">
              <div className="prose max-w-none">
                <div className="bg-[#E6F7F7] border-l-4 border-[#00AFAA] p-4 rounded-r-lg mb-6 text-sm text-[#000000]">
                  <p>
                    <span className="font-semibold">Kategori:</span> {selectedDoc.category || "Ukjent"}
                  </p>
                  <p>
                    <span className="font-semibold">Forfatter:</span> {selectedDoc.author || "Ukjent"}
                  </p>
                </div>

                <h3 className="text-xl text-[#000000] font-semibold mb-4">Dokumentinnhold</h3>

                {selectedDocLoading ? (
                  <p className="text-base text-[#000000] leading-relaxed mb-4">Henter dokument...</p>
                ) : (
                  <pre className="whitespace-pre-wrap text-sm text-[#000000] leading-relaxed bg-white border border-[#000000]/10 rounded-lg p-4">
                    {selectedDocContent || ""}
                  </pre>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
