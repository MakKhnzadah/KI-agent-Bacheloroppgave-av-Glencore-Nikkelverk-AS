import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from "react";
import { documentService } from "@/services";

export interface Document {
  id: string;
  title: string;
  fileName: string;
  category: string;
  status: "pending" | "approved" | "rejected";
  isProcessing?: boolean;
  generationMode?: "ai" | "fallback";
  generationReason?: string;
  uploadedBy: string;
  uploadedAt: string;
  originalContent: string;
  revisedContent: string;
  approvedContent?: string; // The version that was actually approved (either original or revised)
}

interface DocumentsContextType {
  documents: Document[];
  addDocument: (doc: {
    file: File;
    title?: string;
    category: string;
    uploadedBy: string;
  }) => Promise<void>;
  loadOriginalContent: (id: string) => Promise<string>;
  approveDocument: (id: string) => Promise<void>;
  rejectDocument: (id: string) => Promise<void>;
  deleteDocument: (id: string) => Promise<void>;
  getPendingDocuments: () => Document[];
  getRejectedDocuments: () => Document[];
  getApprovedDocuments: () => Document[];
  isLoading: boolean;
}

const DocumentsContext = createContext<DocumentsContextType | undefined>(undefined);

export function DocumentsProvider({ children }: { children: ReactNode }) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const loadDocuments = useCallback(async (showLoading: boolean) => {
    try {
      if (showLoading) {
        setIsLoading(true);
      }
      const docs = await documentService.getAllDocuments();
      setDocuments(docs);
    } catch (error) {
      console.error("Failed to load documents:", error);
    } finally {
      if (showLoading) {
        setIsLoading(false);
      }
    }
  }, []);

  // Initial load
  useEffect(() => {
    void loadDocuments(true);
  }, [loadDocuments]);

  // Poll while any uploaded suggestion is still being processed by KI.
  useEffect(() => {
    const hasProcessing = documents.some((doc) => doc.isProcessing);
    if (!hasProcessing) {
      return;
    }

    const id = window.setInterval(() => {
      void loadDocuments(false);
    }, 3000);

    return () => window.clearInterval(id);
  }, [documents, loadDocuments]);

  const addDocument = async (doc: { file: File; title?: string; category: string; uploadedBy: string }) => {
    try {
      const newDoc = await documentService.uploadDocument({
        file: doc.file,
        title: doc.title,
        category: doc.category as any,
        uploadedBy: doc.uploadedBy,
      });
      
      setDocuments((prev) => [newDoc, ...prev]);
    } catch (error) {
      console.error("Failed to add document:", error);
      throw error;
    }
  };

  const loadOriginalContent = async (id: string): Promise<string> => {
    const existing = documents.find((d) => d.id === id);
    if (existing?.originalContent) {
      return existing.originalContent;
    }

    try {
      const text = await documentService.getOriginalContent(id);
      setDocuments((prev) => prev.map((d) => (d.id === id ? { ...d, originalContent: text } : d)));
      return text;
    } catch (error) {
      console.error("Failed to load original content:", error);
      throw error;
    }
  };

  const approveDocument = async (id: string) => {
    try {
      const updatedDoc = await documentService.approveDocument(id);
      
      setDocuments((prev) =>
        prev.map((doc) => (doc.id === id ? updatedDoc : doc))
      );
    } catch (error) {
      console.error("Failed to approve document:", error);
      throw error;
    }
  };

  const rejectDocument = async (id: string) => {
    try {
      const updatedDoc = await documentService.rejectDocument(id);
      
      setDocuments((prev) =>
        prev.map((doc) => (doc.id === id ? updatedDoc : doc))
      );
    } catch (error) {
      console.error("Failed to reject document:", error);
      throw error;
    }
  };

  const deleteDocument = async (id: string) => {
    try {
      await documentService.deleteDocument(id);
      
      setDocuments((prev) => prev.filter((doc) => doc.id !== id));
    } catch (error) {
      console.error("Failed to delete document:", error);
      throw error;
    }
  };

  // Helper functions for filtering documents by status
  const getPendingDocuments = () => {
    return documents.filter((doc) => doc.status === "pending");
  };

  const getRejectedDocuments = () => {
    return documents.filter((doc) => doc.status === "rejected");
  };

  const getApprovedDocuments = () => {
    return documents.filter((doc) => doc.status === "approved");
  };

  return (
    <DocumentsContext.Provider
      value={{
        documents,
        addDocument,
        loadOriginalContent,
        approveDocument,
        rejectDocument,
        deleteDocument,
        getPendingDocuments,
        getRejectedDocuments,
        getApprovedDocuments,
        isLoading,
      }}
    >
      {children}
    </DocumentsContext.Provider>
  );
}

export function useDocuments() {
  const context = useContext(DocumentsContext);
  if (context === undefined) {
    throw new Error("useDocuments must be used within a DocumentsProvider");
  }
  return context;
}