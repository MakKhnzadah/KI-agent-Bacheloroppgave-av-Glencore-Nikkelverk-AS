/**
 * Service for document management and processing.
 */

import { Document, DocumentUpload, DocumentStats } from "@/types";
import { mockDocuments } from "@/data/mock-documents";
import { authService, ServiceError } from "@/services/authService";

class DocumentService {
  /**
   * Get all documents
   * TODO: Replace with API call when backend is ready
   * Example: const response = await fetch('/api/documents');
   */
  async getAllDocuments(): Promise<Document[]> {
    return await this.requestJson<Document[]>("/api/documents");
  }

  /**
   * Get document by ID
   */
  async getDocumentById(id: string): Promise<Document | null> {
    try {
      return await this.requestJson<Document>(`/api/documents/${encodeURIComponent(id)}`);
    } catch (error) {
      if (error instanceof ServiceError && error.status === 404) {
        return null;
      }
      throw error;
    }
  }

  /**
   * Get pending documents
   */
  async getPendingDocuments(): Promise<Document[]> {
    return await this.requestJson<Document[]>("/api/documents?status=pending");
  }

  /**
   * Get approved documents
   */
  async getApprovedDocuments(): Promise<Document[]> {
    return await this.requestJson<Document[]>("/api/documents?status=approved");
  }

  /**
   * Get rejected documents
   */
  async getRejectedDocuments(): Promise<Document[]> {
    return await this.requestJson<Document[]>("/api/documents?status=rejected");
  }

  /**
   * Upload new document
   */
  async uploadDocument(upload: Partial<DocumentUpload>): Promise<Document> {
    const payload = {
      title: upload.title || "Untitled Document",
      fileName: upload.fileName || "document.pdf",
      category: upload.category || "Annet",
      uploadedBy: upload.uploadedBy || "Ukjent bruker",
      originalContent: upload.originalContent || "",
      revisedContent: upload.revisedContent || "",
    };

    return await this.requestJson<Document>("/api/documents", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  /**
   * Approve document
   */
  async approveDocument(id: string): Promise<Document> {
    const response = await this.requestWithAuthRetry(`/api/documents/${encodeURIComponent(id)}/approve`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });

    return await response.json();
  }

  /**
   * Reject document
   */
  async rejectDocument(id: string): Promise<Document> {
    const response = await this.requestWithAuthRetry(`/api/documents/${encodeURIComponent(id)}/reject`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });

    return await response.json();
  }

  /**
   * Delete document
   */
  async deleteDocument(id: string): Promise<void> {
    await this.requestWithAuthRetry(`/api/documents/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  }

  private async requestWithAuthRetry(path: string, init: RequestInit): Promise<Response> {
    const firstToken = authService.getToken();
    if (!firstToken) {
      throw new ServiceError("You need to log in before performing this action", 401, "UNAUTHORIZED");
    }

    const first = await fetch(path, this.withBearer(init, firstToken));
    if (first.ok) {
      return first;
    }

    if (first.status !== 401) {
      throw await this.readServiceError(first, "Request failed");
    }

    try {
      const refreshedToken = await authService.refreshToken();
      const retry = await fetch(path, this.withBearer(init, refreshedToken));
      if (!retry.ok) {
        throw await this.readServiceError(retry, "Request failed");
      }
      return retry;
    } catch (error) {
      if (error instanceof ServiceError) {
        throw error;
      }

      throw new ServiceError("Session expired. Please log in again", 401, "UNAUTHORIZED");
    }
  }

  private withBearer(init: RequestInit, token: string): RequestInit {
    const headers = new Headers(init.headers);
    headers.set("Authorization", `Bearer ${token}`);

    return {
      ...init,
      headers,
    };
  }

  private async requestJson<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(path, init);
    if (!response.ok) {
      throw await this.readServiceError(response, "Request failed");
    }
    return (await response.json()) as T;
  }

  private async readServiceError(response: Response, fallbackMessage: string): Promise<ServiceError> {
    try {
      const payload = await response.json();
      const nestedError = payload?.error ?? payload?.detail?.error;
      const message = nestedError?.message ?? fallbackMessage;
      const code = nestedError?.code;
      const details = nestedError?.details;
      return new ServiceError(message, response.status, code, details);
    } catch {
      return new ServiceError(fallbackMessage, response.status);
    }
  }

  /**
   * Get document statistics
   */
  async getDocumentStats(): Promise<DocumentStats> {
    await this.simulateDelay(200);
    
    return {
      total: mockDocuments.length,
      pending: mockDocuments.filter(d => d.status === "pending").length,
      approved: mockDocuments.filter(d => d.status === "approved").length,
      rejected: mockDocuments.filter(d => d.status === "rejected").length,
    };
    
    // Future: const response = await fetch('/api/documents/stats');
  }

  /**
   * Search documents
   */
  async searchDocuments(query: string): Promise<Document[]> {
    await this.simulateDelay(300);
    
    const lowerQuery = query.toLowerCase();
    return mockDocuments.filter(doc => 
      doc.title.toLowerCase().includes(lowerQuery) ||
      doc.fileName.toLowerCase().includes(lowerQuery) ||
      doc.category.toLowerCase().includes(lowerQuery)
    );
    
    // Future: const response = await fetch(`/api/documents/search?q=${query}`);
  }

  /**
   * Filter documents by category
   */
  async filterByCategory(category: string): Promise<Document[]> {
    await this.simulateDelay(200);
    
    return mockDocuments.filter(doc => doc.category === category);
    
    // Future: const response = await fetch(`/api/documents?category=${category}`);
  }

  /**
   * Simulate network delay (for development only)
   */
  private simulateDelay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// Export singleton instance
export const documentService = new DocumentService();