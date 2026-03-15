/**
 * User Types for Glencore Knowledge Management System
 */

export type UserRole = "admin" | "user" | "viewer";

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  department?: string;
  avatar?: string;
}

export interface UserActivity {
  id: string;
  userId: string;
  userName: string;
  action: "upload" | "approve" | "reject" | "edit" | "delete";
  documentId?: string;
  documentTitle?: string;
  timestamp: string;
  description: string;
}
