/**
 * Service for document management and processing.
 *
 * Wired to the FastAPI workflow endpoints:
 * - POST /documents/upload
 * - GET /workflow/suggestions (+ GET /workflow/suggestions/{id})
 * - POST /workflow/suggestions/{id}/review
 * - POST /workflow/suggestions/{id}/apply
 */

import { apiClient } from "./apiClient";
import type { Document, DocumentCategory, DocumentStats } from "@/types";

const PROCESSING_MODEL_MARKER = "__processing__";

type UploadResponse = {
  upload_id: string;
  suggestion_id: string;
  structured_draft: string;
  suggestion_addon: string;
  status: string;
  deduped?: boolean;
};

type SuggestionListItem = {
  suggestion_id: string;
  upload_id: string;
  status: string;
  created_at: string;
  original_filename?: string | null;
};

type SuggestionDetail = {
  suggestion_id: string;
  upload_id: string;
  status: string;
  model?: string | null;
  suggestion_json: string;
  created_at: string;
};

function normalizeStatus(status: string): Document["status"] {
  const s = (status || "").toLowerCase();
  if (s === "rejected") return "rejected";
  if (s === "approved" || s === "applied") return "approved";
  return "pending";
}

function formatUploadedAt(sqliteDateTime: string | undefined): string {
  if (!sqliteDateTime) return "";
  // Expect "YYYY-MM-DD HH:MM:SS" from SQLite.
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

function pickTitleFromSuggestion(suggestionJson: string, fallback: string): string {
  const fm = extractFrontMatter(suggestionJson);
  if (fm.title) return fm.title;
  const heading = suggestionJson.match(/^#\s+(.+)$/m);
  return (heading?.[1] || "").trim() || fallback;
}

function pickCategoryFromSuggestion(suggestionJson: string): DocumentCategory {
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

function toDocumentFromSuggestion(listItem: SuggestionListItem, detail: SuggestionDetail): Document {
  const fileName = listItem.original_filename || "document";
  const revised = detail.suggestion_json || "";
  const title = pickTitleFromSuggestion(revised, fileName);
  const category = pickCategoryFromSuggestion(revised);
  const status = normalizeStatus(detail.status);

  return {
    id: detail.suggestion_id,
    title,
    fileName,
    category,
    status,
    isProcessing: detail.model === PROCESSING_MODEL_MARKER,
    uploadedBy: "System",
    uploadedAt: formatUploadedAt(detail.created_at || listItem.created_at),
    originalContent: "",
    revisedContent: revised,
    approvedContent: status === "approved" ? revised : undefined,
  };
}

class DocumentService {
  async getAllDocuments(): Promise<Document[]> {
    const items = await apiClient.getJson<SuggestionListItem[]>("/workflow/suggestions?limit=200&offset=0");
    const details = await Promise.all(
      items.map((s) => apiClient.getJson<SuggestionDetail>(`/workflow/suggestions/${s.suggestion_id}`)),
    );

    return items.map((item, idx) => toDocumentFromSuggestion(item, details[idx]));
  }

  async getPendingDocuments(): Promise<Document[]> {
    const all = await this.getAllDocuments();
    return all.filter((d) => d.status === "pending");
  }

  async getApprovedDocuments(): Promise<Document[]> {
    const all = await this.getAllDocuments();
    return all.filter((d) => d.status === "approved");
  }

  async getRejectedDocuments(): Promise<Document[]> {
    const all = await this.getAllDocuments();
    return all.filter((d) => d.status === "rejected");
  }

  async getDocumentById(id: string): Promise<Document | null> {
    try {
      const detail = await apiClient.getJson<SuggestionDetail>(`/workflow/suggestions/${id}`);
      const listItem: SuggestionListItem = {
        suggestion_id: detail.suggestion_id,
        upload_id: detail.upload_id,
        status: detail.status,
        created_at: detail.created_at,
        original_filename: null,
      };
      return toDocumentFromSuggestion(listItem, detail);
    } catch {
      return null;
    }
  }

  async uploadDocument(params: {
    file: File;
    title?: string;
    category?: DocumentCategory;
    uploadedBy?: string;
  }): Promise<Document> {
    const form = new FormData();
    form.append("file", params.file);

    const res = await apiClient.postForm<UploadResponse>("/documents/upload", form);

    const revised = [res.structured_draft, res.suggestion_addon].filter(Boolean).join("\n\n").trim();
    const title = (params.title || "").trim() || pickTitleFromSuggestion(revised, params.file.name);
    const category = params.category || pickCategoryFromSuggestion(revised);

    const now = new Date();
    const formattedDate = `${now.getDate()}. ${now.toLocaleDateString("nb-NO", { month: "short" })} ${now.getFullYear()} - ${now.toLocaleTimeString("nb-NO", { hour: "2-digit", minute: "2-digit" })}`;

    return {
      id: res.suggestion_id,
      title,
      fileName: params.file.name,
      category,
      status: normalizeStatus(res.status),
      isProcessing: true,
      uploadedBy: params.uploadedBy || "Ukjent bruker",
      uploadedAt: formattedDate,
      originalContent: "",
      revisedContent: revised,
      approvedContent: undefined,
    };
  }

  async approveDocument(id: string, reviewer?: string): Promise<Document> {
    await apiClient.postJson(`/workflow/suggestions/${id}/review`, {
      decision: "approved",
      reviewer: reviewer || "System",
    }, { requireAuth: true });

    await apiClient.postJson(`/workflow/suggestions/${id}/apply`, {}, { requireAuth: true });

    const updated = await this.getDocumentById(id);
    if (!updated) throw new Error("Document not found after approval");
    return updated;
  }

  async rejectDocument(id: string, reviewer?: string): Promise<Document> {
    await apiClient.postJson(`/workflow/suggestions/${id}/review`, {
      decision: "rejected",
      reviewer: reviewer || "System",
    }, { requireAuth: true });

    const updated = await this.getDocumentById(id);
    if (!updated) throw new Error("Document not found after rejection");
    return updated;
  }

  async deleteDocument(_id: string): Promise<void> {
    await apiClient.delete(`/workflow/suggestions/${_id}`, { requireAuth: true });
  }

  async getDocumentStats(): Promise<DocumentStats> {
    const docs = await this.getAllDocuments();
    return {
      total: docs.length,
      pending: docs.filter((d) => d.status === "pending").length,
      approved: docs.filter((d) => d.status === "approved").length,
      rejected: docs.filter((d) => d.status === "rejected").length,
    };
  }

  async searchDocuments(query: string): Promise<Document[]> {
    const q = (query || "").trim();
    if (!q) return [];

    const all = await this.getAllDocuments();
    const lower = q.toLowerCase();
    return all.filter(
      (d) =>
        d.title.toLowerCase().includes(lower) ||
        d.fileName.toLowerCase().includes(lower) ||
        d.category.toLowerCase().includes(lower) ||
        d.revisedContent.toLowerCase().includes(lower),
    );
  }

  async filterByCategory(category: string): Promise<Document[]> {
    const all = await this.getAllDocuments();
    return all.filter((d) => d.category === (category as any));
  }
}

export const documentService = new DocumentService();
