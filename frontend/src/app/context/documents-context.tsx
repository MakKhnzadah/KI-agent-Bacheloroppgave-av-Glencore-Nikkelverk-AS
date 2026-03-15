import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { documentService } from "@/services";

export interface Document {
  id: string;
  title: string;
  fileName: string;
  category: string;
  status: "pending" | "approved" | "rejected";
  uploadedBy: string;
  uploadedAt: string;
  originalContent: string;
  revisedContent: string;
  approvedContent?: string; // The version that was actually approved (either original or revised)
}

interface DocumentsContextType {
  documents: Document[];
  addDocument: (doc: Omit<Document, "id" | "uploadedAt" | "status">) => Promise<void>;
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

  // Load initial data from documentService
  useEffect(() => {
    async function loadDocuments() {
      try {
        setIsLoading(true);
        const docs = await documentService.getAllDocuments();
        setDocuments(docs);
      } catch (error) {
        console.error("Failed to load documents:", error);
      } finally {
        setIsLoading(false);
      }
    }

    loadDocuments();
  }, []);

  const addDocument = async (doc: Omit<Document, "id" | "uploadedAt" | "status">) => {
    try {
      const newDoc = await documentService.uploadDocument({
        ...doc,
        category: doc.category as any,
        originalContent: doc.originalContent,
        revisedContent: doc.revisedContent,
      });
      
      setDocuments((prev) => [newDoc, ...prev]);
    } catch (error) {
      console.error("Failed to add document:", error);
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