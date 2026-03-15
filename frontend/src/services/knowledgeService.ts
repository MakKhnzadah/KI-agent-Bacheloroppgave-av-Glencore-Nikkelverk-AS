/**
 * Service for knowledge bank search and retrieval.
 */

import { Document } from "@/types";
import { documentService } from "./documentService";

class KnowledgeService {
  /**
   * Get all approved documents for knowledge bank
   */
  async getKnowledgeDocuments(): Promise<Document[]> {
    return await documentService.getApprovedDocuments();
    
    // Future:
    // const response = await fetch('/api/knowledge/documents');
    // return await response.json();
  }

  /**
   * Search knowledge bank
   */
  async searchKnowledge(query: string): Promise<Document[]> {
    const allApproved = await this.getKnowledgeDocuments();
    
    const lowerQuery = query.toLowerCase();
    return allApproved.filter(doc => 
      doc.title.toLowerCase().includes(lowerQuery) ||
      doc.category.toLowerCase().includes(lowerQuery) ||
      doc.approvedContent?.toLowerCase().includes(lowerQuery)
    );
    
    // Future:
    // const response = await fetch(`/api/knowledge/search?q=${query}`);
    // return await response.json();
  }

  /**
   * Get knowledge by category
   */
  async getKnowledgeByCategory(category: string): Promise<Document[]> {
    const allApproved = await this.getKnowledgeDocuments();
    return allApproved.filter(doc => doc.category === category);
    
    // Future:
    // const response = await fetch(`/api/knowledge/category/${category}`);
    // return await response.json();
  }

  /**
   * Get related documents
   */
  async getRelatedDocuments(documentId: string, limit: number = 5): Promise<Document[]> {
    const document = await documentService.getDocumentById(documentId);
    if (!document) return [];
    
    const allApproved = await this.getKnowledgeDocuments();
    
    // Simple related logic: same category, excluding current document
    const related = allApproved
      .filter(doc => doc.id !== documentId && doc.category === document.category)
      .slice(0, limit);
    
    return related;
    
    // Future (with AI-powered similarity):
    // const response = await fetch(`/api/knowledge/related/${documentId}?limit=${limit}`);
    // return await response.json();
  }

  /**
   * Get knowledge statistics by category
   */
  async getCategoryStats(): Promise<Record<string, number>> {
    const allApproved = await this.getKnowledgeDocuments();
    const stats: Record<string, number> = {};
    allApproved.forEach(doc => {
      stats[doc.category] = (stats[doc.category] || 0) + 1;
    });
    
    return stats;
    
    // Future:
    // const response = await fetch('/api/knowledge/stats/categories');
    // return await response.json();
  }

  /**
   * Get most recent knowledge documents
   */
  async getRecentDocuments(limit: number = 10): Promise<Document[]> {
    const allApproved = await this.getKnowledgeDocuments();
    return allApproved
      .sort((a, b) => {
        return b.uploadedAt.localeCompare(a.uploadedAt);
      })
      .slice(0, limit);
    
    // Future:
    // const response = await fetch(`/api/knowledge/recent?limit=${limit}`);
    // return await response.json();
  }

  /**
   * Export document as PDF
   * Note: This would require backend processing
   */
  async exportDocumentAsPDF(documentId: string): Promise<Blob> {
    const document = await documentService.getDocumentById(documentId);
    if (!document) throw new Error("Document not found");
    
    // Mock: Create a simple text blob
    const content = document.approvedContent || document.revisedContent;
    const blob = new Blob([content], { type: 'text/plain' });
    
    return blob;
    
    // Future:
    // const response = await fetch(`/api/knowledge/export/${documentId}/pdf`);
    // return await response.blob();
  }
}

// Export singleton instance
export const knowledgeService = new KnowledgeService();
