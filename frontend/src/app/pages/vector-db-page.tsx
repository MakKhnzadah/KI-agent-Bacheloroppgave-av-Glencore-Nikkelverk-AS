import { useEffect, useMemo, useState } from "react";
import { Trash2 } from "lucide-react";

import { Sidebar } from "@/app/components/sidebar";
import { documentService } from "@/services/documentService";
import { useToast } from "@/app/context/toast-context";
import { getAuthPermissionErrorMessage } from "@/utils/auth-errors";

type VectorDbDocument = {
  path: string;
  kb_path?: string | null;
  title: string;
  doc_id?: string | null;
  doc_hash?: string | null;
  chunk_count: number;
};

type RawKbDocument = {
  kb_path: string;
  title: string;
  author: string;
  date: string;
  category: string;
};

export function VectorDbPage() {
  const { showToast } = useToast();

  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [deletingRaw, setDeletingRaw] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [docs, setDocs] = useState<VectorDbDocument[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [meta, setMeta] = useState<{ persist_dir?: string; collection?: string } | null>(null);

  const [rawLoading, setRawLoading] = useState(false);
  const [rawError, setRawError] = useState<string | null>(null);
  const [rawDocs, setRawDocs] = useState<RawKbDocument[]>([]);
  const [rawTotal, setRawTotal] = useState<number>(0);

  const subtitle = useMemo(() => {
    const parts: string[] = [];
    if (meta?.collection) parts.push(`Collection: ${meta.collection}`);
    if (meta?.persist_dir) parts.push(`Persist dir: ${meta.persist_dir}`);
    return parts.join(" · ");
  }, [meta]);

  const load = () => {
    setLoading(true);
    setError(null);

    (async () => {
      try {
        const res = await documentService.listVectorDbDocuments({ limit: 2000, offset: 0 });
        setDocs(res.documents || []);
        setTotal(res.total_documents || 0);
        setMeta({ persist_dir: res.persist_dir, collection: res.collection });
      } catch (e) {
        setError(`Klarte ikke å hente filer. ${getAuthPermissionErrorMessage(e)}`);
      } finally {
        setLoading(false);
      }
    })();
  };

  const loadRaw = () => {
    setRawLoading(true);
    setRawError(null);

    (async () => {
      try {
        const res = await documentService.listKnowledgeBankDocuments({ limit: 2000, offset: 0, category: "All" });
        setRawDocs((res.documents || []) as RawKbDocument[]);
        setRawTotal(res.total || 0);
      } catch (e) {
        setRawError(`Klarte ikke å hente råfiler. ${getAuthPermissionErrorMessage(e)}`);
      } finally {
        setRawLoading(false);
      }
    })();
  };

  useEffect(() => {
    load();
    loadRaw();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSync = async () => {
    try {
      setSyncing(true);
      const res = await documentService.reindexVectorDb();
      const files = res.indexed?.files;
      const chunks = res.indexed?.chunks;
      showToast(
        typeof files === "number" && typeof chunks === "number"
          ? `Synkronisert (${files} filer, ${chunks} tekstbiter).`
          : "Synkronisert.",
        "success",
        7000,
      );
      load();
      loadRaw();
    } catch (e) {
      showToast(`Klarte ikke å synkronisere. ${getAuthPermissionErrorMessage(e)}`, "error", 9000);
    } finally {
      setSyncing(false);
    }
  };

  const handleDelete = async (doc: VectorDbDocument) => {
    const kbPath = (doc.kb_path || "").trim();
    if (!kbPath) {
      showToast("Kan ikke slette: mangler kb_path for dokumentet.", "error");
      return;
    }

    const ok = window.confirm(`Slette '${doc.title}' fra vector DB? Dette fjerner alle tekstbiter (chunks) for dokumentet.`);
    if (!ok) return;

    try {
      setDeleting(kbPath);
      await documentService.deleteVectorDbDocument(kbPath);
      setDocs((prev) => prev.filter((d) => (d.kb_path || "").trim() !== kbPath));
      setTotal((prev) => Math.max(0, prev - 1));
      showToast("Dokumentet ble slettet fra vector DB.", "success");
    } catch (e) {
      showToast(`Klarte ikke å slette dokumentet. ${getAuthPermissionErrorMessage(e)}`, "error");
    } finally {
      setDeleting(null);
    }
  };

  const handleDeleteRaw = async (doc: RawKbDocument) => {
    const kbPath = (doc.kb_path || "").trim();
    if (!kbPath) {
      showToast("Kan ikke slette: mangler kb_path for råfilen.", "error");
      return;
    }

    const ok = window.confirm(`Slette '${doc.title}' fra råfiler? Dette fjerner kildefilen før indeksering.`);
    if (!ok) return;

    try {
      setDeletingRaw(kbPath);
      await documentService.deleteKnowledgeBankDocument(kbPath, true);

      setRawDocs((prev) => prev.filter((d) => (d.kb_path || "").trim() !== kbPath));
      setRawTotal((prev) => Math.max(0, prev - 1));

      const removedIndexed = docs.filter((d) => (d.kb_path || "").trim() === kbPath).length;
      if (removedIndexed > 0) {
        setDocs((prev) => prev.filter((d) => (d.kb_path || "").trim() !== kbPath));
        setTotal((prev) => Math.max(0, prev - removedIndexed));
      }

      showToast("Råfilen ble slettet.", "success");
    } catch (e) {
      showToast(`Klarte ikke å slette råfilen. ${getAuthPermissionErrorMessage(e)}`, "error");
    } finally {
      setDeletingRaw(null);
    }
  };

  return (
    <div className="flex h-screen bg-white">
      <Sidebar />

      <div className="flex-1 flex flex-col overflow-hidden bg-[#00afaa1a]">
        <header className="flex items-center justify-between h-[103px] px-6 bg-[#ededed] border border-[#ededed] flex-shrink-0 mx-6">
          <div>
            <h1 className="text-2xl text-[#000000] font-semibold">Filer</h1>
            <p className="text-xs text-[#000000]/60 mt-1">{subtitle || ""}</p>
          </div>

          <div className="text-sm text-[#000000]/70 font-semibold">
            {loading || rawLoading ? "Laster..." : `Råfiler: ${rawTotal} · Indeksert: ${total}`}
          </div>
        </header>

        <div className="flex-1 overflow-y-auto px-6 pb-6 pt-4">
          <div className="bg-white border border-white">
            <div className="px-6 py-4 border-b border-[#000000]/10 flex items-center justify-between">
              <p className="text-sm text-[#000000]/70">
                Råfiler er kildene før indeksering. Indeksert er tekstbitene i vector DB. Du kan slette begge deler her.
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleSync}
                  className={`px-4 py-2 rounded-lg transition-colors text-sm font-semibold ${syncing
                    ? "bg-[#000000]/10 text-[#000000]/50 cursor-not-allowed"
                    : "bg-[#00AFAA] hover:bg-[#00AFAA]/90 text-white"
                    }`}
                  disabled={syncing}
                >
                  {syncing ? "Synkroniserer..." : "Synkroniser"}
                </button>
                <button
                  onClick={() => {
                    load();
                    loadRaw();
                  }}
                  className="px-4 py-2 bg-white border border-[#000000]/20 hover:bg-[#F5F5F5] text-[#000000] rounded-lg transition-colors text-sm font-semibold"
                  disabled={loading || rawLoading}
                >
                  Oppdater
                </button>
              </div>
            </div>

            {(rawError || error) && (
              <div className="px-6 py-4 text-sm text-[#7C0D15] bg-[#FCEBEC] border-b border-[#000000]/10">
                {rawError || error}
              </div>
            )}

            <div className="px-6 py-4 border-b border-[#000000]/10">
              <p className="text-xs font-semibold text-[#000000]/60 mb-2">RÅFILER (DISK)</p>
              {!rawError && !rawLoading && rawDocs.length === 0 && (
                <p className="text-sm text-[#000000]/60">Ingen råfiler funnet i kunnskapsbasen.</p>
              )}
              <div className="space-y-2">
                {rawDocs.slice(0, 30).map((d) => (
                  <div key={d.kb_path} className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <p className="text-sm text-[#000000] font-semibold truncate">{d.title || "(uten tittel)"}</p>
                      <p className="text-xs text-[#000000]/60 break-all">{d.kb_path}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-xs text-[#000000]/60 whitespace-nowrap">{d.category}</div>
                      <button
                        onClick={() => handleDeleteRaw(d)}
                        disabled={deletingRaw === d.kb_path}
                        className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition-colors ${
                          deletingRaw === d.kb_path
                            ? "bg-[#000000]/5 text-[#000000]/40 cursor-not-allowed"
                            : "bg-[#FCEBEC] text-[#7C0D15] hover:bg-[#F8D3D6]"
                        }`}
                        title="Slett råfil (før indeksering)"
                      >
                        <Trash2 className="w-4 h-4" />
                        {deletingRaw === d.kb_path ? "Sletter..." : "Slett"}
                      </button>
                    </div>
                  </div>
                ))}
                {rawTotal > 30 && (
                  <p className="text-xs text-[#000000]/60">… og {rawTotal - 30} til.</p>
                )}
              </div>
            </div>

            <div className="px-6 py-4">
              <p className="text-xs font-semibold text-[#000000]/60 mb-2">INDEKSERT (VECTOR DB)</p>
              {!error && !loading && docs.length === 0 && (
                <p className="text-sm text-[#000000]/60">Ingen indekserte filer funnet.</p>
              )}
            </div>

            <div className="divide-y divide-[#000000]/10">
              {docs.map((d) => {
                const kbPath = (d.kb_path || "").trim();
                const labelPath = kbPath || d.path;
                const isDeleting = deleting === kbPath && !!kbPath;

                return (
                  <div key={labelPath} className="px-6 py-4 flex items-start justify-between gap-6">
                    <div className="min-w-0 flex-1">
                      <p className="text-base text-[#000000] font-semibold truncate">{d.title || "(uten tittel)"}</p>
                      <p className="text-xs text-[#000000]/60 mt-1 break-all">{labelPath}</p>
                      <p className="text-xs text-[#000000]/60 mt-1">Chunks: {d.chunk_count}</p>
                    </div>

                    <button
                      onClick={() => handleDelete(d)}
                      disabled={!kbPath || isDeleting}
                      className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition-colors ${
                        !kbPath || isDeleting
                          ? "bg-[#000000]/5 text-[#000000]/40 cursor-not-allowed"
                          : "bg-[#FCEBEC] text-[#7C0D15] hover:bg-[#F8D3D6]"
                      }`}
                      title={!kbPath ? "Mangler kb_path (kan ikke slette deterministisk)." : "Slett indekserte tekstbiter"}
                    >
                      <Trash2 className="w-4 h-4" />
                      {isDeleting ? "Sletter..." : "Slett"}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
