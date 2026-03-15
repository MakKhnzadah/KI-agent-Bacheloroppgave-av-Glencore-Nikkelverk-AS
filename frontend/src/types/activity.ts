/**
 * Activity Types for Dashboard
 */

export type ActivityType = 
  | "document_approved" 
  | "document_uploaded" 
  | "ai_suggestion" 
  | "document_rejected"
  | "system_update";

export interface Activity {
  id: string;
  type: ActivityType;
  title: string;
  description: string;
  user: string;
  time: string;
  documentId?: string;
}
