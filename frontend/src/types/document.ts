/**
 * Document Types for Glencore Knowledge Management System
 */

export type DocumentStatus = "pending" | "approved" | "rejected";

export type DocumentCategory = 
  | "Sikkerhet" 
  | "Vedlikehold" 
  | "Miljø" 
  | "Kvalitet" 
  | "Prosedyre"
  | "Annet";

export interface Document {
  id: string;
  title: string;
  fileName: string;
  category: DocumentCategory;
  status: DocumentStatus;
  uploadedBy: string;
  uploadedAt: string;
  originalContent: string;
  revisedContent: string;
  approvedContent?: string; // The version that was actually approved
}

export interface DocumentUpload {
  title: string;
  fileName: string;
  category: DocumentCategory;
  uploadedBy: string;
  originalContent: string;
  revisedContent: string;
}

export interface DocumentStats {
  total: number;
  pending: number;
  approved: number;
  rejected: number;
}
