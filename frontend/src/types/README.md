# Types - Glencore Knowledge Management System

## 📋 Overview

This directory contains all TypeScript type definitions and interfaces for the application. These types ensure type safety throughout the codebase.

---

## 🗂️ Types Structure

```
/src/types/
├── document.ts     # Document-related types
├── user.ts         # User & activity types
├── auth.ts         # Authentication types
├── activity.ts     # Activity feed types
└── index.ts        # Central type exports
```

---

## 📝 Type Definitions

### 1. **document.ts**

#### DocumentStatus
```typescript
type DocumentStatus = "pending" | "approved" | "rejected";
```

#### DocumentCategory
```typescript
type DocumentCategory = 
  | "Sikkerhet"     // Safety
  | "Vedlikehold"   // Maintenance
  | "Miljø"         // Environment
  | "Kvalitet"      // Quality
  | "Prosedyre"     // Procedure
  | "Annet";        // Other
```

#### Document Interface
```typescript
interface Document {
  id: string;
  title: string;
  fileName: string;
  category: DocumentCategory;
  status: DocumentStatus;
  uploadedBy: string;
  uploadedAt: string;
  originalContent: string;
  revisedContent: string;
  approvedContent?: string;
}
```

#### DocumentUpload Interface
```typescript
interface DocumentUpload {
  title: string;
  fileName: string;
  category: DocumentCategory;
  uploadedBy: string;
  originalContent: string;
  revisedContent: string;
}
```

#### DocumentStats Interface
```typescript
interface DocumentStats {
  total: number;
  pending: number;
  approved: number;
  rejected: number;
}
```

---

### 2. **user.ts**

#### UserRole
```typescript
type UserRole = "admin" | "user" | "viewer";
```

#### User Interface
```typescript
interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  department?: string;
  avatar?: string;
}
```

#### UserActivity Interface
```typescript
interface UserActivity {
  id: string;
  userId: string;
  userName: string;
  action: "upload" | "approve" | "reject" | "edit" | "delete";
  documentId?: string;
  documentTitle?: string;
  timestamp: string;
  description: string;
}
```

---

### 3. **auth.ts**

#### LoginCredentials Interface
```typescript
interface LoginCredentials {
  email: string;
  password: string;
}
```

#### AuthResponse Interface
```typescript
interface AuthResponse {
  user: User;
  token: string;
  expiresAt: string;
}
```

#### AuthState Interface
```typescript
interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}
```

---

### 4. **activity.ts**

#### ActivityType
```typescript
type ActivityType = 
  | "document_approved" 
  | "document_uploaded" 
  | "ai_suggestion" 
  | "document_rejected"
  | "system_update";
```

#### Activity Interface
```typescript
interface Activity {
  id: string;
  type: ActivityType;
  title: string;
  description: string;
  user: string;
  time: string;
  documentId?: string;
}
```

---

## 💡 Usage Examples

### Import Types

```typescript
// Import all types from central export
import type { Document, User, Activity } from '@/types';

// Import specific types
import type { DocumentStatus, UserRole } from '@/types';

// Import from specific file
import type { Document } from '@/types/document';
```

### Using Document Types

```typescript
// Define a document variable
const doc: Document = {
  id: "1",
  title: "Safety Procedure",
  fileName: "safety.pdf",
  category: "Sikkerhet",
  status: "pending",
  uploadedBy: "John Doe",
  uploadedAt: "12. mar 2026",
  originalContent: "...",
  revisedContent: "..."
};

// Type-safe function
function approveDocument(doc: Document): Document {
  return { ...doc, status: "approved" };
}
```

### Using Auth Types

```typescript
// Login credentials
const credentials: LoginCredentials = {
  email: "admin@glencore.com",
  password: "admin123"
};

// Auth response
const handleLogin = async (creds: LoginCredentials): Promise<AuthResponse> => {
  const response = await authService.login(creds);
  return response;
};
```

### Using Activity Types

```typescript
// Create activity
const activity: Activity = {
  id: "1",
  type: "document_approved",
  title: "Document Approved",
  description: "Safety procedure approved",
  user: "Admin",
  time: "now",
  documentId: "123"
};
```

---

## 🎯 Benefits

✅ **Type Safety** - Catch errors at compile time  
✅ **IntelliSense** - Auto-completion in VS Code  
✅ **Documentation** - Types serve as documentation  
✅ **Refactoring** - Safe refactoring with TypeScript  
✅ **Consistency** - Enforce data structure consistency  

---

## 🔄 Type Guards

You can create type guards for runtime type checking:

```typescript
// Check document status
function isPending(doc: Document): boolean {
  return doc.status === "pending";
}

// Type guard
function isAdmin(user: User): boolean {
  return user.role === "admin";
}
```

---

## 📦 Integration with Services

Types are used by services for type-safe API calls:

```typescript
// documentService.ts
async uploadDocument(upload: DocumentUpload): Promise<Document> {
  // TypeScript ensures correct data structure
  const response = await fetch('/api/documents', {
    method: 'POST',
    body: JSON.stringify(upload) // Type-checked!
  });
  return await response.json();
}
```

---

## 🔧 Extending Types

To add new fields or types:

1. Update the appropriate type file
2. Update mock data if needed
3. Update services using the type
4. Update components using the type

Example:

```typescript
// Add new category
type DocumentCategory = 
  | "Sikkerhet"
  | "Vedlikehold"
  | "Miljø"
  | "Kvalitet"
  | "Prosedyre"
  | "Opplæring"  // ← New category
  | "Annet";
```

---

## 📊 Type Relationships

```
Document
├── status: DocumentStatus
├── category: DocumentCategory
└── uploadedBy: string (from User.name)

Activity
├── type: ActivityType
├── user: string (from User.name)
└── documentId?: string (from Document.id)

AuthResponse
├── user: User
├── token: string
└── expiresAt: string
```

---

## 🚀 Best Practices

1. ✅ Always use types for function parameters and return values
2. ✅ Use `interface` for object shapes
3. ✅ Use `type` for unions and primitives
4. ✅ Mark optional fields with `?`
5. ✅ Export types from `index.ts` for easy imports
6. ✅ Keep types close to their usage domain

---

## 📝 Notes

- All types are exported from `/src/types/index.ts`
- Types match the mock data structure in `/src/data/mock-documents.ts`
- Types align with service method signatures in `/src/services/`
- Norwegian field names match Glencore Norway requirements
