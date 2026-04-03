import { useEffect, useState, type ReactNode } from "react";
import { Sidebar } from "@/app/components/sidebar";
import { MessageSquare, FileText, Clock, ChevronRight, X, Send, XCircle, Trash2 } from "lucide-react";
import { useDocuments } from "@/app/context/documents-context";
import { useToast } from "@/app/context/toast-context";
import { documentService } from "@/services";
import { getAuthPermissionErrorMessage } from "@/utils/auth-errors";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import remarkGfm from "remark-gfm";

const MARKDOWN_COMPONENTS: Components = {
  h1: ({ children }: { children?: ReactNode }) => <h1 className="text-xl font-semibold mb-4 mt-2">{children}</h1>,
  h2: ({ children }: { children?: ReactNode }) => <h2 className="text-lg font-semibold mb-3 mt-5">{children}</h2>,
  h3: ({ children }: { children?: ReactNode }) => <h3 className="text-base font-semibold mb-2 mt-4">{children}</h3>,
  p: ({ children }: { children?: ReactNode }) => <p className="mb-3 whitespace-pre-wrap">{children}</p>,
  ul: ({ children }: { children?: ReactNode }) => <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>,
  ol: ({ children }: { children?: ReactNode }) => <ol className="list-decimal pl-5 mb-3 space-y-1">{children}</ol>,
  li: ({ children }: { children?: ReactNode }) => <li className="whitespace-pre-wrap">{children}</li>,
  blockquote: ({ children }: { children?: ReactNode }) => (
    <blockquote className="border-l-4 border-[#000000]/10 pl-4 my-4 text-[#000000]/80">{children}</blockquote>
  ),
  code: ({ children }: { children?: ReactNode }) => (
    <code className="px-1 py-0.5 rounded bg-[#000000]/5 font-mono text-[0.85em]">{children}</code>
  ),
  pre: ({ children }: { children?: ReactNode }) => (
    <pre className="mb-4 overflow-x-auto rounded border border-[#000000]/10 bg-[#000000]/5 p-3 text-xs">{children}</pre>
  ),
  table: ({ children }: { children?: ReactNode }) => (
    <div className="mb-4 overflow-x-auto">
      <table className="w-full border-collapse text-xs">{children}</table>
    </div>
  ),
  th: ({ children }: { children?: ReactNode }) => <th className="border border-[#000000]/10 bg-[#000000]/5 px-2 py-1 text-left">{children}</th>,
  td: ({ children }: { children?: ReactNode }) => <td className="border border-[#000000]/10 px-2 py-1 align-top">{children}</td>,
  a: ({ href, children }: { href?: string; children?: ReactNode }) => (
    <a href={href} target="_blank" rel="noreferrer" className="underline">
      {children}
    </a>
  ),
};

interface ChatMessage {
  role: "user" | "ai";
  content: string;
}

type SimilarityMatch = {
  kb_path: string;
  title?: string | null;
  jaccard: number;
  coverage_new: number;
  coverage_existing: number;
};

type ReindexStatus = {
  state: string;
  last_error?: string | null;
  last_indexed_files?: number | null;
  last_indexed_chunks?: number | null;
};

function stripYamlFrontMatter(markdown: string): string {
  // Preview-only: suggestions are stored as "YAML front matter + Markdown body".
  // Rendering the YAML as plain text makes long documents harder to read.
  const raw = markdown || "";
  // Normalize BOM + line endings so we can reliably detect --- blocks on Windows.
  const text = raw.replace(/^\ufeff/, "").replace(/\r\n/g, "\n").replace(/^\s+/, "");
  if (!text.startsWith("---\n")) return text;
  const end = text.indexOf("\n---\n", 4);
  if (end === -1) return text;
  return text.slice(end + "\n---\n".length).replace(/^\n+/, "");
}

function looksLikeMarkdown(content: string): boolean {
  const text = content.replace(/\r\n/g, "\n");
  return (
    /^#{1,6}\s+\S/m.test(text) ||
    /^\s*([-*+]\s+\S|\d+\.\s+\S)/m.test(text) ||
    /^>\s+\S/m.test(text) ||
    /^```/m.test(text) ||
    /\|/.test(text)
  );
}

function looksLikeGluedText(content: string): boolean {
  const text = (content || "").replace(/\r\n/g, "\n");
  const sample = text.replace(/\s+/g, " ").trim();
  if (sample.length < 400) return false;
  const words = sample.split(" ").filter(Boolean);
  if (words.length === 0) return false;
  const avgLen = words.reduce((sum, w) => sum + w.length, 0) / words.length;
  const longTokens = words.filter(w => w.length >= 40).length;
  const spaceRatio = sample.split("").filter(ch => ch === " ").length / sample.length;
  return longTokens >= 8 || (spaceRatio < 0.055 && avgLen > 11);
}

function looksLikeDocumentDraft(content: string): boolean {
  const text = (content || "").replace(/\r\n/g, "\n").trim();
  if (!text) return false;
  if (text.startsWith("---\n")) return true;
  if (/^#{1,6}\s+\S/m.test(text)) return true;
  if (/^\d+(?:\.\d+)*\s+\S/m.test(text)) return true;
  if (text.split("\n").length >= 14 && text.length >= 1200) return true;
  return false;
}

function looksLikeChattyReply(content: string): boolean {
  const text = (content || "").trim();
  if (!text) return false;
  if (/\b(i\s*['’]d\s+be\s+happy\s+to\s+help|before\s+we\s+begin|please\s+confirm|is\s+that\s+correct)\b/i.test(text)) return true;
  if (/\b(før\s+vi\s+begynner|har\s+du\s+noen\s+preferanser|er\s+det\s+korrekt)\b/i.test(text)) return true;
  const q = (text.match(/\?/g) || []).length;
  if (q >= 2 && text.length < 2500) return true;
  return false;
}

function normalizeExtractedText(content: string): string {
  // Preview-only: help readability for PDF-extracted text artifacts.
  let text = (content || "").replace(/\r\n/g, "\n");

  // Fix common private-use glyph issues in URLs like "hps" -> "https".
  text = text.replace(/h[\uE000-\uF8FF]ps:\/\//gi, "https://");
  text = text.replace(/h[\uE000-\uF8FF]p:\/\//gi, "http://");
  text = text.replace(/[\uE000-\uF8FF]/g, "");

  // De-hyphenate common line-break hyphenation like "in- cluding".
  text = text.replace(/(\w)-\s+(\w)/g, "$1$2");

  // Add missing spaces after punctuation so sentence splitting works.
  text = text.replace(/([.,;:!?])(\S)/g, "$1 $2");
  text = text.replace(/(\))(\S)/g, "$1 $2");
  text = text.replace(/(\S)(\()/g, "$1 $2");

  // Collapse excessive spaces while keeping newlines (paragraph detection uses them).
  text = text.replace(/[ \t\f\v]+/g, " ");
  text = text.replace(/\n{3,}/g, "\n\n");
  return text.trim();
}

function coercePlainTextToMarkdown(content: string): string {
  // Preview-only: try to render common PDF/plain-text structures as readable Markdown.
  const raw = (content || "").replace(/\r\n/g, "\n");
  if (!raw.trim()) return "";

  const stripDotLeadersAndPageNo = (s: string): { text: string; pageNo?: string } => {
    // Typical TOC/LOF/LOT lines contain dot leaders and a trailing page number:
    // "1.1 Background . . . 1" or "11 Qt Creator[25] . . . 17".
    const noLeaders = s.replace(/(\s*\.(?:\s*\.)+\s*)/g, " ").replace(/\s{2,}/g, " ").trim();
    const m = noLeaders.match(/^(.*?)(?:\s+(\d+|[ivxlcdm]{1,6}))\s*$/i);
    if (!m) return { text: noLeaders };
    const text = (m[1] || "").trim();
    const pageNo = (m[2] || "").trim();
    if (!text) return { text: noLeaders };
    return { text, pageNo };
  };

  const isLikelyStandalonePageMarker = (line: string): boolean => {
    if (/^page\s+\d+$/i.test(line)) return true;
    // Roman numerals used as page markers in front matter.
    if (/^[ivxlcdm]{1,6}$/i.test(line)) return true;
    return false;
  };

  const normalizeDuplicateNumberedHeading = (line: string): string | null => {
    // Common PDF artifact: "2 THEORY 2 Theory" or "1 INTRODUCTION 1 Introduction".
    // Prefer the part that contains lowercase letters.
    const m = line.match(/^\s*(\d+(?:\.\d+)*)\s+(.+?)\s+\1\s+(.+?)\s*$/);
    if (!m) return null;
    const numbering = m[1];
    const partA = m[2].trim();
    const partB = m[3].trim();
    const pick = /[a-zæøå]/.test(partB) ? partB : partA;
    return `${numbering} ${pick}`;
  };

  const lines = raw.split("\n");
  const out: string[] = [];

  const pushBlank = () => {
    if (out.length === 0) return;
    if (out[out.length - 1] !== "") out.push("");
  };

  let tocMode: "none" | "toc" | "lof" | "lot" = "none";

  for (let i = 0; i < lines.length; i += 1) {
    const original = lines[i] ?? "";
    let line = original.replace(/[ \t\f\v]+/g, " ").trim();
    if (!line) {
      // Keep at most one blank line.
      if (out.length > 0 && out[out.length - 1] !== "") out.push("");
      continue;
    }

    // Split cases like "Contents 1 Introduction 1" into two lines.
    const combined = line.match(/^(contents|list of figures|list of tables|nomenclature)\s+(.+)$/i);
    if (combined) {
      const head = combined[1];
      const rest = (combined[2] || "").trim();
      if (rest) {
        lines.splice(i + 1, 0, rest);
      }
      line = head;
    }

    // Drop standalone page markers.
    if (isLikelyStandalonePageMarker(line)) {
      continue;
    }

    // Section markers that often introduce structured index blocks.
    if (/^contents$/i.test(line)) {
      pushBlank();
      out.push("## Contents");
      pushBlank();
      tocMode = "toc";
      continue;
    }
    if (/^list of figures$/i.test(line)) {
      pushBlank();
      out.push("## List of Figures");
      pushBlank();
      tocMode = "lof";
      continue;
    }
    if (/^list of tables$/i.test(line)) {
      pushBlank();
      out.push("## List of Tables");
      pushBlank();
      tocMode = "lot";
      continue;
    }

    // TOC / List-of-* entries.
    if (tocMode !== "none") {
      // End the index block when we hit a new top-level chapter heading.
      if (/^\d+\s+[A-Z][A-Z\s]{3,}$/i.test(line) && !/\s\d+$/i.test(line)) {
        tocMode = "none";
        // fall through to normal handling below
      } else {
        // Normalize dot leaders and strip trailing page markers.
        const cleaned = stripDotLeadersAndPageNo(line);

        // Contents: numbered outline entries.
        const tocEntry = cleaned.text.match(/^(\d+(?:\.\d+)*)\s+(.+)$/);
        if (tocEntry && tocMode === "toc") {
          const numbering = tocEntry[1];
          const title = tocEntry[2].trim();
          const depth = numbering.split(".").length;
          const indent = " ".repeat(Math.max(0, (depth - 1) * 2));
          out.push(`${indent}- ${numbering} ${title}`);
          continue;
        }

        // List of Figures/Tables: entries often look like "1 caption ... 14".
        const listEntry = cleaned.text.match(/^(\d+)\s+(.+)$/);
        if (listEntry && (tocMode === "lof" || tocMode === "lot")) {
          const n = listEntry[1];
          const caption = listEntry[2].trim();
          const label = tocMode === "lof" ? "Figure" : "Table";
          out.push(`- ${label} ${n}: ${caption}`);
          continue;
        }

        // If we can't parse it, keep it as plain text to avoid losing information.
        out.push(cleaned.text);
        continue;
      }
    }

    // Normalize duplicated headings like "2 THEORY 2 Theory".
    const normalizedDupHeading = normalizeDuplicateNumberedHeading(line);
    if (normalizedDupHeading) {
      line = normalizedDupHeading;
    }

    // Convert bullet glyphs.
    if (line.startsWith("• ") || line === "•") {
      out.push(line === "•" ? "-" : `- ${line.slice(2).trim()}`);
      continue;
    }

    // Figures/Tables.
    const figOrTable = line.match(/^(figure|table)\s+(\d+)\s*:\s*(.+)$/i);
    if (figOrTable) {
      pushBlank();
      const label = figOrTable[1][0].toUpperCase() + figOrTable[1].slice(1).toLowerCase();
      out.push(`**${label} ${figOrTable[2]}:** ${figOrTable[3].trim()}`);
      pushBlank();
      continue;
    }

    // Numbered headings (e.g., "1 INTRODUCTION", "2.1 Project Control").
    const numbered = line.match(/^(\d+(?:\.\d+)*)\s+(.+?)$/);
    if (numbered) {
      const numbering = numbered[1];
      const title = numbered[2].trim();
      // Avoid treating pure TOC lines like "1 Introduction 1" as headings.
      // If it ends with a lone page number and has no punctuation, keep as plain text.
      if (/\s(\d+|[ivxlcdm]{1,6})$/i.test(title) && !/[.:;!?]/.test(title)) {
        const cleaned = stripDotLeadersAndPageNo(line);
        out.push(cleaned.text);
        continue;
      }

      const depth = numbering.split(".").length;
      const level = Math.min(6, Math.max(2, 1 + depth)); // 1 -> ##, 1.1 -> ###, 1.1.1 -> ####
      pushBlank();
      out.push(`${"#".repeat(level)} ${numbering} ${title}`);
      pushBlank();
      continue;
    }

    // ALL CAPS headings (common in PDFs).
    if (/^[A-Z][A-Z\s]{6,}$/.test(line) && line.length <= 80) {
      pushBlank();
      out.push(`## ${line}`);
      pushBlank();
      continue;
    }

    out.push(line);
  }

  // Clean up: collapse multiple blank lines.
  const collapsed: string[] = [];
  for (const l of out) {
    if (l === "" && collapsed[collapsed.length - 1] === "") continue;
    collapsed.push(l);
  }

  return collapsed.join("\n").trim();
}

function autoParagraphPlainText(content: string): string {
  // Preview-only: many PDFs become a single huge paragraph after extraction.
  // This tries to split into readable paragraphs without changing stored content.
  const text = (content || "").replace(/\r\n/g, "\n").trim();
  if (!text) return "";
  if (/\n\n+/.test(text)) return text; // already has paragraphs

  // Chunk by sentence-ish boundaries to create paragraphs.
  const targetMin = 450;
  const targetMax = 900;
  const out: string[] = [];
  let i = 0;
  while (i < text.length) {
    const maxEnd = Math.min(i + targetMax, text.length);
    const windowText = text.slice(i, maxEnd);

    // Find last sentence boundary in the window.
    let cut = -1;
    for (let j = windowText.length - 1; j >= 0; j -= 1) {
      const ch = windowText[j];
      if (ch === "." || ch === "!" || ch === "?") {
        // Prefer boundaries that are followed by whitespace.
        const next = windowText[j + 1];
        if (next === undefined || /\s/.test(next)) {
          cut = j + 1;
          break;
        }
      }
    }

    // If we didn't find a boundary, fall back to last space.
    if (cut === -1) {
      const space = windowText.lastIndexOf(" ");
      cut = space > targetMin ? space : windowText.length;
    }

    // If cut is too small, just take a bigger chunk.
    if (cut < targetMin) {
      cut = Math.min(windowText.length, targetMax);
    }

    const chunk = text.slice(i, i + cut).trim();
    if (chunk) out.push(chunk);
    i += cut;

    // Skip whitespace between chunks
    while (i < text.length && /\s/.test(text[i])) i += 1;
  }

  return out.join("\n\n");
}

function MarkdownPreview({ content }: { content: string }) {
  const stripped = stripYamlFrontMatter(content);
  if (looksLikeMarkdown(stripped)) {
    return (
      <div className="mx-auto max-w-3xl text-sm text-[#000000] leading-relaxed">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={MARKDOWN_COMPONENTS}
        >
          {stripped}
        </ReactMarkdown>
      </div>
    );
  }

  const normalized = looksLikeGluedText(stripped) ? normalizeExtractedText(stripped) : stripped;
  const coerced = coercePlainTextToMarkdown(normalized);
  const previewMarkdown = looksLikeMarkdown(coerced) ? coerced : autoParagraphPlainText(coerced);

  return (
    <div className="mx-auto max-w-3xl text-sm text-[#000000] leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={MARKDOWN_COMPONENTS}
      >
        {previewMarkdown}
      </ReactMarkdown>
    </div>
  );
}

export function QueuePage() {
  const { getPendingDocuments, getRejectedDocuments, loadOriginalContent, approveDocument, rejectDocument, deleteDocument } = useDocuments();
  const { showToast } = useToast();
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [revisedContent, setRevisedContent] = useState("");
  const [viewRejectedDoc, setViewRejectedDoc] = useState<string | null>(null);
  const [viewingOriginal, setViewingOriginal] = useState(false);

  const [similarityLoading, setSimilarityLoading] = useState(false);
  const [similarityError, setSimilarityError] = useState<string | null>(null);
  const [similarityMatches, setSimilarityMatches] = useState<SimilarityMatch[] | null>(null);
  const [reindexStatus, setReindexStatus] = useState<ReindexStatus>({ state: "unknown" });

  const [chatSending, setChatSending] = useState(false);

  const documents = getPendingDocuments();
  const rejectedDocuments = getRejectedDocuments();
  const selectedDocument = documents.find(doc => doc.id === selectedDocId);
  const viewedRejectedDocument = rejectedDocuments.find(doc => doc.id === viewRejectedDoc);

  const selectedIsPdf = !!selectedDocument?.fileName && selectedDocument.fileName.toLowerCase().endsWith(".pdf");
  const viewedRejectedIsPdf = !!viewedRejectedDocument?.fileName && viewedRejectedDocument.fileName.toLowerCase().endsWith(".pdf");

  const handleDocumentSelect = (docId: string) => {
    const doc = documents.find(d => d.id === docId);
    setSelectedDocId(docId);
    setRevisedContent(doc?.revisedContent || "");
    setChatMessages([]);
    setViewingOriginal(false);
    setSimilarityMatches(null);
    setSimilarityError(null);
  };

  useEffect(() => {
    if (!selectedDocId) {
      setSimilarityMatches(null);
      setSimilarityError(null);
      setSimilarityLoading(false);
      return;
    }

    if (selectedDocument?.isProcessing) {
      setSimilarityMatches(null);
      setSimilarityError(null);
      setSimilarityLoading(false);
      return;
    }

    let cancelled = false;
    setSimilarityLoading(true);
    setSimilarityError(null);

    void (async () => {
      try {
        const res = await documentService.getSuggestionSimilarity(selectedDocId, { limit: 5, minCoverageNew: 0.05 });
        if (cancelled) return;
        setSimilarityMatches(res.matches || []);
      } catch (e) {
        if (cancelled) return;
        console.error("Failed to load similarity:", e);
        setSimilarityError(`Klarte ikke å sjekke likhet. ${getAuthPermissionErrorMessage(e)}`);
        setSimilarityMatches([]);
      } finally {
        if (cancelled) return;
        setSimilarityLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [selectedDocId, selectedDocument?.isProcessing]);

  useEffect(() => {
    let cancelled = false;

    const loadReindexStatus = async () => {
      try {
        const status = await documentService.getKnowledgeBankReindexStatus();
        if (cancelled) return;
        setReindexStatus({
          state: status.state || "unknown",
          last_error: status.last_error,
          last_indexed_files: status.last_indexed_files,
          last_indexed_chunks: status.last_indexed_chunks,
        });
      } catch (error) {
        if (cancelled) return;
        console.error("Failed to load reindex status:", error);
        setReindexStatus({ state: "unavailable", last_error: getAuthPermissionErrorMessage(error) });
      }
    };

    void loadReindexStatus();
    const id = window.setInterval(() => {
      void loadReindexStatus();
    }, 15000);

    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  const normalizedReindexState = (reindexStatus.state || "unknown").toLowerCase();
  const reindexStatusLabel =
    normalizedReindexState === "completed"
      ? "Fullfort"
      : normalizedReindexState === "in_progress"
        ? "Pågår"
        : normalizedReindexState === "scheduled"
          ? "Planlagt"
          : normalizedReindexState === "failed"
            ? "Feilet"
            : normalizedReindexState === "skipped"
              ? "Hoppet over"
              : normalizedReindexState === "idle"
                ? "Inaktiv"
                : "Ukjent";

  const reindexStatusToneClass =
    normalizedReindexState === "completed"
      ? "bg-[#0B6A46]/10 text-[#0B6A46]"
      : normalizedReindexState === "in_progress" || normalizedReindexState === "scheduled"
        ? "bg-[#005B7F]/10 text-[#005B7F]"
        : normalizedReindexState === "failed" || normalizedReindexState === "skipped" || normalizedReindexState === "unavailable"
          ? "bg-[#B3232F]/10 text-[#7C0D15]"
          : "bg-[#000000]/10 text-[#333333]";

  const handleShowOriginal = async () => {
    if (!selectedDocId) return;
    try {
      if (!selectedIsPdf) {
        await loadOriginalContent(selectedDocId);
      }
      setViewingOriginal(true);
    } catch (error) {
      console.error("Failed to load original content:", error);
      showToast(`Klarte ikke å hente originalt dokument. ${getAuthPermissionErrorMessage(error)}`, "error");
    }
  };

  const handleApprove = async () => {
    if (selectedDocId) {
      try {
        await approveDocument(selectedDocId);
        showToast("Dokument godkjent. AI-revidert versjon er lagret i kunnskapsbanken. Indeksering pågår.", "success");

        void (async () => {
          try {
            const status = await documentService.waitForKnowledgeBankReindexCompletion({ intervalMs: 5000 });
            const state = (status.state || "").toLowerCase();

            if (state === "completed") {
              const files = status.last_indexed_files ?? 0;
              const chunks = status.last_indexed_chunks ?? 0;
              showToast(`Indeksering fullført (${files} filer, ${chunks} tekstbiter).`, "success");
              return;
            }

            if (state === "failed" || state === "skipped" || state === "timeout") {
              const reason = (status.last_error || "Ukjent årsak").trim();
              showToast(`Dokumentet ble lagret, men indeksering ble ikke fullført: ${reason}`, "error", 9000);
            }
          } catch (error) {
            console.error("Failed to fetch reindex status:", error);
            showToast(`Dokumentet ble lagret, men vi klarte ikke å hente indekseringsstatus. ${getAuthPermissionErrorMessage(error)}`, "error", 9000);
          }
        })();

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
    const msg = inputMessage.trim();
    if (!msg || chatSending) return;
    if (!selectedDocId) return;

    const wantsSimilarityCheck = /\b(sjekk|check|kontroller)\b/i.test(msg) && /\b(likhet|overlapp)\b/i.test(msg);

    const userMessage: ChatMessage = { role: "user", content: msg };
    setChatMessages(prev => [...prev, userMessage]);
    setInputMessage("");
    setChatSending(true);

    void (async () => {
      try {
        if (wantsSimilarityCheck) {
          const res = await documentService.checkSimilarityForDocument(revisedContent, { limit: 5, minCoverageNew: 0.05 });
          const matches = res.matches || [];
          setSimilarityMatches(matches);
          setSimilarityError(null);

          if (matches.length === 0) {
            setChatMessages(prev => [...prev, { role: "ai", content: "Jeg fant ingen tydelig overlapp mot kunnskapsbanken i denne versjonen." }]);
            return;
          }

          const top = matches.slice(0, 3).map((m) => {
            const pct = Math.round((m.coverage_new || 0) * 100);
            const title = (m.title || m.kb_path).trim();
            return `- ${pct}%: ${title}`;
          });
          setChatMessages(prev => [
            ...prev,
            {
              role: "ai",
              content: `Her er topp-treffene mot kunnskapsbanken (andel av ditt dokument som overlapper):\n${top.join("\n")}`,
            },
          ]);
          return;
        }

        const res = await documentService.reviseDocument({
          document: revisedContent,
          instruction: msg,
        });

        const updated = (res.updated_document || "").trim();
        const message = (res.message || "").trim();
        const updatedLooksChatty = looksLikeChattyReply(updated) && !looksLikeDocumentDraft(updated) && !looksLikeMarkdown(updated);

        // Safety guard: never overwrite the revised draft with a chat-style reply.
        const chatText = updatedLooksChatty ? updated : (message || "Oppdatert dokumentet.");
        setChatMessages(prev => [...prev, { role: "ai", content: chatText }]);

        if (updated && !updatedLooksChatty) {
          setRevisedContent(updated);

          // Refresh similarity for the updated draft (without requiring a re-select of the suggestion).
          try {
            setSimilarityLoading(true);
            const sim = await documentService.checkSimilarityForDocument(updated, { limit: 5, minCoverageNew: 0.05 });
            setSimilarityMatches(sim.matches || []);
            setSimilarityError(null);
          } catch (e) {
            console.error("Failed to refresh similarity:", e);
            setSimilarityError(`Klarte ikke å sjekke likhet. ${getAuthPermissionErrorMessage(e)}`);
          } finally {
            setSimilarityLoading(false);
          }
        }
      } catch (error) {
        console.error("Failed to send chat message:", error);
        showToast(`Feil ved sending til AI. ${getAuthPermissionErrorMessage(error)}`, "error");
        setChatMessages(prev => [...prev, { role: "ai", content: "Jeg fikk ikke kontakt med AI akkurat nå." }]);
      } finally {
        setChatSending(false);
      }
    })();
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
                <div className="flex items-start justify-between mb-6 gap-4">
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

                  <div className="bg-white border border-[#000000]/10 rounded-lg p-4 min-w-[260px]">
                    <div className="flex items-center justify-between gap-3 mb-2">
                      <p className="text-sm font-semibold text-[#000000]">KB indeksering</p>
                      <span className={`px-2 py-0.5 rounded text-xs font-semibold ${reindexStatusToneClass}`}>
                        {reindexStatusLabel}
                      </span>
                    </div>
                    {normalizedReindexState === "completed" ? (
                      <p className="text-xs text-[#000000]/70">
                        {reindexStatus.last_indexed_files ?? 0} filer, {reindexStatus.last_indexed_chunks ?? 0} tekstbiter
                      </p>
                    ) : null}
                    {normalizedReindexState === "failed" || normalizedReindexState === "skipped" || normalizedReindexState === "unavailable" ? (
                      <p className="text-xs text-[#7C0D15] line-clamp-2">{(reindexStatus.last_error || "Ukjent feil").trim()}</p>
                    ) : null}
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
                           onClick={() => void (async () => {
                             try {
                               await loadOriginalContent(doc.id);
                             } catch (error) {
                               console.error("Failed to load original content:", error);
                             }
                             setViewRejectedDoc(doc.id);
                           })()}
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
                    onClick={() => void handleShowOriginal()}
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
                  <div className={selectedIsPdf ? "max-w-5xl mx-auto" : "max-w-4xl mx-auto"}>
                    <h3 className="text-xl text-[#000000] font-semibold mb-8">{selectedDocument.title}</h3>
                    {selectedIsPdf ? (
                      <iframe
                        title={selectedDocument.fileName}
                        src={documentService.getOriginalFileUrl(selectedDocId)}
                        className="w-full h-[520px] border border-[#000000]/10 rounded"
                      />
                    ) : (
                      <div className="text-sm text-[#000000] leading-relaxed whitespace-pre-wrap">
                        {selectedDocument.originalContent}
                      </div>
                    )}
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
                        <MarkdownPreview content={revisedContent} />
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
                      <div className="p-4 bg-white rounded-lg border border-[#000000]/10">
                        <p className="text-xs font-semibold text-[#000000] mb-2">Likhet mot kunnskapsbanken</p>
                        {selectedDocument?.isProcessing ? (
                          <p className="text-xs text-[#000000]/70">AI behandler dokumentet – likhet sjekkes etterpå.</p>
                        ) : similarityLoading ? (
                          <p className="text-xs text-[#000000]/70">Sjekker overlapp...</p>
                        ) : similarityError ? (
                          <p className="text-xs text-[#82131E]">{similarityError}</p>
                        ) : (similarityMatches && similarityMatches.length > 0) ? (
                          <div className="space-y-2">
                            {similarityMatches.map((m) => (
                              <div key={m.kb_path} className="text-xs text-[#000000]">
                                <div className="flex items-baseline justify-between gap-3">
                                  <p className="font-semibold truncate">{m.title || m.kb_path}</p>
                                  <p className="text-[#00AFAA] font-semibold flex-shrink-0">{Math.round((m.coverage_new || 0) * 100)}%</p>
                                </div>
                                <p className="text-[#000000]/60 truncate">{m.kb_path}</p>
                              </div>
                            ))}
                            <p className="text-[11px] text-[#000000]/60 pt-1">Prosent = hvor mye av det nye dokumentet som overlapper.</p>
                          </div>
                        ) : (
                          <p className="text-xs text-[#000000]/70">Ingen tydelig overlapp funnet.</p>
                        )}
                      </div>

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
                          disabled={!inputMessage.trim() || chatSending}
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
                <MarkdownPreview content={viewedRejectedDocument.revisedContent} />
              </div>

              <h3 className="text-lg text-[#000000] font-semibold mb-4">Original innhold</h3>
              <div className="bg-white border border-[#000000]/10 rounded-lg p-6">
                {viewedRejectedIsPdf ? (
                  <iframe
                    title={viewedRejectedDocument.fileName}
                    src={documentService.getOriginalFileUrl(viewedRejectedDocument.id)}
                    className="w-full h-[420px] border border-[#000000]/10 rounded"
                  />
                ) : (
                  <p className="text-sm text-[#000000] leading-relaxed whitespace-pre-wrap">
                    {viewedRejectedDocument.originalContent}
                  </p>
                )}
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