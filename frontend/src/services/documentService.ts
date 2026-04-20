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
import {
  normalizeStatus,
  pickCategoryFromSuggestion,
  pickTitleFromSuggestion,
  toDocumentFromSuggestion,
  type SuggestionDetailForMapping,
  type SuggestionListItemForMapping,
} from "./documentService.mappers";

const PROCESSING_MODEL_MARKER = "__processing__";

type UploadResponse = {
  upload_id: string;
  suggestion_id: string;
  structured_draft: string;
  suggestion_addon: string;
  status: string;
  model?: string;
  prompt_version?: string;
  processing?: boolean;
  deduped?: boolean;
};

type SuggestionListItem = SuggestionListItemForMapping;

type SuggestionDetail = SuggestionDetailForMapping & {
  model?: string | null;
  prompt_version?: string | null;
  generation_attempts?: number | null;
  generation_started_at?: string | null;
  generation_finished_at?: string | null;
  generation_error?: string | null;
};

type SuggestionOriginal = {
  suggestion_id: string;
  upload_id: string;
  original_filename?: string | null;
  text: string;
};

type SimilarityMatch = {
  kb_path: string;
  title?: string | null;
  jaccard: number;
  coverage_new: number;
  coverage_existing: number;
};

type SimilarityResponse = {
  suggestion_id: string;
  matches: SimilarityMatch[];
};

type SimilarityCheckRequest = {
  document: string;
};

type SimilarityCheckResponse = {
  matches: SimilarityMatch[];
};

type ReviseRequest = {
  document: string;
  instruction: string;
};

type ReviseResponse = {
  message: string;
  updated_document: string;
};

type KnowledgeSource = {
  id: string;
  title: string;
  author: string;
  date: string;
  category: string;
  retrievalMethod?: "vector" | "lexical";
};

type KnowledgeChatTurn = {
  role: "user" | "bot";
  message: string;
};

type KnowledgeChatRequest = {
  message: string;
  category?: string;
  history?: KnowledgeChatTurn[];
};

type KnowledgeChatResponse = {
  answer: string;
  sources: KnowledgeSource[];
};

type KbStatsResponse = {
  total: number;
  by_category: Record<string, number>;
};

type KbDocumentResponse = {
  id: string;
  kb_path: string;
  title: string;
  author: string;
  date: string;
  category: string;
  content: string;
};

type KbDocumentListItem = {
  kb_path: string;
  title: string;
  author: string;
  date: string;
  category: string;
};

type KbDocumentsListResponse = {
  total: number;
  returned: number;
  offset: number;
  limit: number;
  documents: KbDocumentListItem[];
};

type KbReindexStatusResponse = {
  state: string;
  current_run_id?: string | null;
  last_completed_run_id?: string | null;
  last_reason?: string | null;
  last_started_at?: string | null;
  last_finished_at?: string | null;
  last_error?: string | null;
  last_indexed_files?: number | null;
  last_indexed_chunks?: number | null;
};

type VectorDbDocument = {
  path: string;
  kb_path?: string | null;
  title: string;
  doc_id?: string | null;
  doc_hash?: string | null;
  chunk_count: number;
};

type VectorDbListResponse = {
  total_documents: number;
  returned: number;
  offset: number;
  limit: number;
  documents: VectorDbDocument[];
  persist_dir?: string;
  collection?: string;
};

type VectorDbReindexResponse = {
  status: string;
  indexed?: {
    files?: number;
    chunks?: number;
  };
  persist_dir?: string;
};


class DocumentService {
  getOriginalFileUrl(suggestionId: string, options?: { render?: "pdf" }): string {
    const base = `${apiClient.baseUrl}/workflow/suggestions/${suggestionId}/file`;
    if (!options?.render) return base;
    const qs = new URLSearchParams({ render: options.render });
    return `${base}?${qs.toString()}`;
  }

  async getSuggestionSimilarity(
    suggestionId: string,
    params?: {
      limit?: number;
      minCoverageNew?: number;
      excludeKbPath?: string;
    },
  ): Promise<SimilarityResponse> {
    const qs = new URLSearchParams();
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.minCoverageNew !== undefined) qs.set("min_coverage_new", String(params.minCoverageNew));
    if (params?.excludeKbPath) qs.set("exclude_kb_path", params.excludeKbPath);

    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return apiClient.getJson<SimilarityResponse>(`/workflow/suggestions/${suggestionId}/similarity${suffix}`);
  }

  async checkSimilarityForDocument(
    document: string,
    params?: {
      limit?: number;
      minCoverageNew?: number;
      excludeKbPath?: string;
    },
  ): Promise<SimilarityCheckResponse> {
    const qs = new URLSearchParams();
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.minCoverageNew !== undefined) qs.set("min_coverage_new", String(params.minCoverageNew));
    if (params?.excludeKbPath) qs.set("exclude_kb_path", params.excludeKbPath);

    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    const body: SimilarityCheckRequest = { document: document || "" };
    return apiClient.postJson<SimilarityCheckResponse>(`/workflow/similarity-check${suffix}`, body);
  }

  async reviseDocument(params: ReviseRequest): Promise<ReviseResponse> {
    return apiClient.postJson<ReviseResponse>("/agent/revise", {
      document: params.document,
      instruction: params.instruction,
    });
  }

  async askKnowledgeBank(params: KnowledgeChatRequest): Promise<KnowledgeChatResponse> {
    return apiClient.postJson<KnowledgeChatResponse>("/agent/knowledge-chat", {
      message: params.message,
      category: params.category,
      history: params.history,
    });
  }

  async getKnowledgeBankStats(): Promise<KbStatsResponse> {
    return apiClient.getJson<KbStatsResponse>("/workflow/kb/stats");
  }

  async getKnowledgeBankDocument(kbPath: string): Promise<KbDocumentResponse> {
    const qs = new URLSearchParams({ kb_path: kbPath });
    return apiClient.getJson<KbDocumentResponse>(`/workflow/kb/document?${qs.toString()}`);
  }

  async listKnowledgeBankDocuments(params?: {
    limit?: number;
    offset?: number;
    category?: string;
  }): Promise<KbDocumentsListResponse> {
    const qs = new URLSearchParams();
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    if (params?.category) qs.set("category", params.category);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return apiClient.getJson<KbDocumentsListResponse>(`/workflow/kb/documents${suffix}`);
  }

  async deleteKnowledgeBankDocument(kbPath: string, deleteIndexed = true): Promise<void> {
    const qs = new URLSearchParams({ kb_path: kbPath, delete_indexed: String(deleteIndexed) });
    await apiClient.delete(`/workflow/kb/documents?${qs.toString()}`, { requireAuth: true });
  }

  async getKnowledgeBankReindexStatus(): Promise<KbReindexStatusResponse> {
    return apiClient.getJson<KbReindexStatusResponse>("/workflow/kb/reindex-status");
  }

  async listVectorDbDocuments(params?: { limit?: number; offset?: number }): Promise<VectorDbListResponse> {
    const qs = new URLSearchParams();
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return apiClient.getJson<VectorDbListResponse>(`/vector/db/documents${suffix}`);
  }

  async deleteVectorDbDocument(kbPath: string): Promise<void> {
    const qs = new URLSearchParams({ kb_path: kbPath });
    await apiClient.delete(`/vector/db/documents?${qs.toString()}`);
  }

  async reindexVectorDb(): Promise<VectorDbReindexResponse> {
    return apiClient.postJson<VectorDbReindexResponse>("/vector/index/kb", {});
  }

  async waitForKnowledgeBankReindexCompletion(options?: {
    timeoutMs?: number;
    intervalMs?: number;
  }): Promise<KbReindexStatusResponse> {
    const timeoutMs = options?.timeoutMs ?? 180000;
    const intervalMs = options?.intervalMs ?? 2000;
    const terminal = new Set(["completed", "failed", "skipped"]);

    const start = Date.now();
    let lastStatus: KbReindexStatusResponse | null = null;
    while (Date.now() - start < timeoutMs) {
      const status = await this.getKnowledgeBankReindexStatus();
      lastStatus = status;
      if (terminal.has((status.state || "").toLowerCase())) {
        return status;
      }
      await new Promise((resolve) => window.setTimeout(resolve, intervalMs));
    }

    return {
      ...(lastStatus ?? {}),
      state: "timeout",
      last_error: `Indekseringen tar lengre tid enn forventet og fortsetter i bakgrunnen (timeout ${Math.round(timeoutMs / 1000)}s).`,
    };
  }

  async getAllDocuments(): Promise<Document[]> {
    const items = await apiClient.getJson<SuggestionListItem[]>("/workflow/suggestions?limit=200&offset=0");
    const details = await Promise.all(
      items.map((s) => apiClient.getJson<SuggestionDetail>(`/workflow/suggestions/${s.suggestion_id}`)),
    );

    return items.map((item, idx) => toDocumentFromSuggestion(item, details[idx]));
  }

  async getOriginalContent(suggestionId: string): Promise<string> {
    const res = await apiClient.getJson<SuggestionOriginal>(`/workflow/suggestions/${suggestionId}/original`);
    return res.text || "";
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

  async updateSuggestionDraft(suggestionId: string, suggestionJson: string): Promise<void> {
    await apiClient.patchJson<SuggestionDetail>(
      `/workflow/suggestions/${suggestionId}`,
      { suggestion_json: suggestionJson },
      { requireAuth: true },
    );
  }

  async uploadDocument(params: {
    file: File;
    title?: string;
    category?: DocumentCategory;
    uploadedBy?: string;
  }): Promise<Document> {
    const form = new FormData();
    form.append("file", params.file);
    if (params.category) form.append("category", params.category);

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
      isProcessing: (res.processing ?? (res.model === PROCESSING_MODEL_MARKER)),
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
