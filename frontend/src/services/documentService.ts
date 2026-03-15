/**
 * Service for document management and processing.
 */

import { Document, DocumentUpload, DocumentStats } from "@/types";
import { mockDocuments } from "@/data/mock-documents";

class DocumentService {
  /**
   * Get all documents
   * TODO: Replace with API call when backend is ready
   * Example: const response = await fetch('/api/documents');
   */
  async getAllDocuments(): Promise<Document[]> {
    // Simulate API delay
    await this.simulateDelay(300);
    
    // Mock implementation
    return [...mockDocuments];
    
    // Future backend implementation:
    // const response = await fetch('/api/documents', {
    //   headers: { 'Authorization': `Bearer ${token}` }
    // });
    // return await response.json();
  }

  /**
   * Get document by ID
   */
  async getDocumentById(id: string): Promise<Document | null> {
    await this.simulateDelay(200);
    
    const document = mockDocuments.find(doc => doc.id === id);
    return document || null;
    
    // Future: const response = await fetch(`/api/documents/${id}`);
  }

  /**
   * Get pending documents
   */
  async getPendingDocuments(): Promise<Document[]> {
    await this.simulateDelay(200);
    
    return mockDocuments.filter(doc => doc.status === "pending");
    
    // Future: const response = await fetch('/api/documents?status=pending');
  }

  /**
   * Get approved documents
   */
  async getApprovedDocuments(): Promise<Document[]> {
    await this.simulateDelay(200);
    
    return mockDocuments.filter(doc => doc.status === "approved");
    
    // Future: const response = await fetch('/api/documents?status=approved');
  }

  /**
   * Get rejected documents
   */
  async getRejectedDocuments(): Promise<Document[]> {
    await this.simulateDelay(200);
    
    return mockDocuments.filter(doc => doc.status === "rejected");
    
    // Future: const response = await fetch('/api/documents?status=rejected');
  }

  /**
   * Upload new document
   */
  async uploadDocument(upload: Partial<DocumentUpload>): Promise<Document> {
    await this.simulateDelay(500);
    
    const now = new Date();
    const formattedDate = `${now.getDate()}. ${now.toLocaleDateString("nb-NO", { month: "short" })} ${now.getFullYear()} - ${now.toLocaleTimeString("nb-NO", { hour: "2-digit", minute: "2-digit" })}`;
    
    const newDoc: Document = {
      id: Date.now().toString(),
      title: upload.title || "Untitled Document",
      fileName: upload.fileName || "document.pdf",
      category: upload.category || "Annet",
      uploadedBy: upload.uploadedBy || "Ukjent bruker",
      uploadedAt: formattedDate,
      status: "pending",
      originalContent: upload.originalContent || `${upload.title || "Untitled Document"}

Dette er det originale dokumentet som ble lastet opp.
Innholdet vil bli analysert og revidert av AI-systemet.

Kategori: ${upload.category || "Annet"}
Fil: ${upload.fileName || "document.pdf"}`,
      revisedContent: upload.revisedContent || `${upload.title || "Untitled Document"} - AI Revidert

Dette er den reviderte versjonen av dokumentet etter AI-analyse.

Følgende forbedringer er implementert:
- Strukturert format i henhold til Glencore standarder
- Lagt til nødvendige sikkerhetsprosedyrer
- Oppdatert referanser til gjeldende regelverk
- Forbedret språk og klarhet

Kategori: ${upload.category || "Annet"}
Fil: ${upload.fileName || "document.pdf"}
Status: Venter på godkjenning

For fullstendig dokumentasjon, se vedlagte detaljer.`,
    };
    
    // Mock: Add to local array
    mockDocuments.unshift(newDoc);
    return newDoc;
    
    // Future:
    // const response = await fetch('/api/documents', {
    //   method: 'POST',
    //   headers: { 'Content-Type': 'application/json' },
    //   body: JSON.stringify(upload)
    // });
    // return await response.json();
  }

  /**
   * Approve document
   */
  async approveDocument(id: string): Promise<Document> {
    await this.simulateDelay(300);
    
    const doc = mockDocuments.find(d => d.id === id);
    if (!doc) throw new Error("Document not found");
    
    doc.status = "approved";
    doc.approvedContent = doc.revisedContent;
    
    return doc;
    
    // Future:
    // const response = await fetch(`/api/documents/${id}/approve`, {
    //   method: 'PATCH'
    // });
  }

  /**
   * Reject document
   */
  async rejectDocument(id: string): Promise<Document> {
    await this.simulateDelay(300);
    
    const doc = mockDocuments.find(d => d.id === id);
    if (!doc) throw new Error("Document not found");
    
    doc.status = "rejected";
    doc.approvedContent = undefined;
    
    return doc;
    
    // Future:
    // const response = await fetch(`/api/documents/${id}/reject`, {
    //   method: 'PATCH'
    // });
  }

  /**
   * Delete document
   */
  async deleteDocument(id: string): Promise<void> {
    await this.simulateDelay(300);
    
    const index = mockDocuments.findIndex(d => d.id === id);
    if (index > -1) {
      mockDocuments.splice(index, 1);
    }
    
    // Future:
    // await fetch(`/api/documents/${id}`, { method: 'DELETE' });
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