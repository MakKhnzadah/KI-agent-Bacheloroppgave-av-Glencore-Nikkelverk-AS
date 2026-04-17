import type { Document, DocumentCategory } from "@/types";

export type SuggestionListItemForMapping = {
  suggestion_id: string;
  upload_id: string;
  status: string;
  created_at: string;
  original_filename?: string | null;
};

export type SuggestionDetailForMapping = {
  suggestion_id: string;
  upload_id: string;
  status: string;
  suggestion_json: string;
  created_at: string;
  generation_status?: string | null;
  generation_fallback_used?: number | null;
  generation_reason?: string | null;
};

export function normalizeStatus(status: string): Document["status"] {
  const s = (status || "").toLowerCase();
  if (s === "rejected") return "rejected";
  if (s === "approved" || s === "applied") return "approved";
  return "pending";
}

function formatUploadedAt(sqliteDateTime: string | undefined): string {
  if (!sqliteDateTime) return "";
  const iso = sqliteDateTime.replace(" ", "T") + "Z";
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return sqliteDateTime;

  const day = dt.getUTCDate();
  const month = dt.toLocaleDateString("nb-NO", { month: "short" });
  const year = dt.getUTCFullYear();
  const hh = dt.getUTCHours().toString().padStart(2, "0");
  const mm = dt.getUTCMinutes().toString().padStart(2, "0");
  return `${day}. ${month} ${year} - ${hh}:${mm}`;
}

function extractFrontMatter(doc: string): Record<string, string> {
  const text = (doc || "").replace(/^\uFEFF/, "");
  if (!text.startsWith("---\n")) return {};

  const lines = text.split("\n");
  let endIdx = -1;
  for (let i = 1; i < lines.length; i += 1) {
    if (lines[i].trim() === "---") {
      endIdx = i;
      break;
    }
  }
  if (endIdx === -1) return {};

  const out: Record<string, string> = {};
  for (const line of lines.slice(1, endIdx)) {
    const m = line.match(/^([A-Za-z0-9_-]+)\s*:\s*(.*)\s*$/);
    if (!m) continue;
    const key = m[1];
    let value = m[2] || "";
    value = value.replace(/^"(.*)"$/, "$1").replace(/^'(.*)'$/, "$1");
    out[key] = value;
  }
  return out;
}

export function pickTitleFromSuggestion(suggestionJson: string, fallback: string): string {
  const fm = extractFrontMatter(suggestionJson);
  if (fm.title) return fm.title;
  const heading = suggestionJson.match(/^#\s+(.+)$/m);
  return (heading?.[1] || "").trim() || fallback;
}

export function pickCategoryFromSuggestion(suggestionJson: string): DocumentCategory {
  const fm = extractFrontMatter(suggestionJson);
  const raw = (fm.category || fm.kategori || "").trim();
  const normalized = raw.toLowerCase();
  if (normalized === "sikkerhet") return "Sikkerhet";
  if (normalized === "vedlikehold") return "Vedlikehold";
  if (normalized === "miljø" || normalized === "miljo") return "Miljø";
  if (normalized === "kvalitet") return "Kvalitet";
  if (normalized === "prosedyre") return "Prosedyre";
  return "Annet";
}

export function toDocumentFromSuggestion(
  listItem: SuggestionListItemForMapping,
  detail: SuggestionDetailForMapping,
): Document {
  const fileName = listItem.original_filename || "document";
  const revised = detail.suggestion_json || "";
  const title = pickTitleFromSuggestion(revised, fileName);
  const category = pickCategoryFromSuggestion(revised);
  const status = normalizeStatus(detail.status);
  const fallbackUsed = Number(detail.generation_fallback_used ?? 0) === 1;

  return {
    id: detail.suggestion_id,
    title,
    fileName,
    category,
    status,
    isProcessing: ["queued", "running"].includes((detail.generation_status || "").toLowerCase()),
    generationMode: fallbackUsed ? "fallback" : "ai",
    generationReason: (detail.generation_reason || "").trim() || undefined,
    uploadedBy: "System",
    uploadedAt: formatUploadedAt(detail.created_at || listItem.created_at),
    originalContent: "",
    revisedContent: revised,
    approvedContent: status === "approved" ? revised : undefined,
  };
}
