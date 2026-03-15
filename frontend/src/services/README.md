# Services Layer - Glencore Knowledge Management System

## 📋 Overview

This directory contains all service modules that handle business logic and API communication. Each service is ready for backend integration with clear TODO comments.

---

## 🗂️ Services Structure

```
/src/services/
├── documentService.ts      # Document CRUD operations
├── authService.ts          # Authentication & authorization
├── knowledgeService.ts     # Knowledge bank operations
├── activityService.ts      # Activity feed management
└── index.ts               # Central exports
```

---

## 🔧 Services Documentation

### 1. **documentService.ts**

Handles all document-related operations:

- `getAllDocuments()` - Fetch all documents
- `getDocumentById(id)` - Get single document
- `getPendingDocuments()` - Get pending approvals
- `getApprovedDocuments()` - Get approved documents
- `getRejectedDocuments()` - Get rejected documents
- `uploadDocument(data)` - Upload new document
- `approveDocument(id)` - Approve document
- `rejectDocument(id)` - Reject document
- `deleteDocument(id)` - Delete document
- `getDocumentStats()` - Get statistics
- `searchDocuments(query)` - Search documents
- `filterByCategory(category)` - Filter by category

### 2. **authService.ts**

Manages user authentication:

- `login(credentials)` - User login
- `logout()` - User logout
- `getCurrentUser()` - Get current user from storage
- `getToken()` - Get auth token
- `isAuthenticated()` - Check auth status
- `refreshToken()` - Refresh auth token
- `verifyToken()` - Verify token validity

### 3. **knowledgeService.ts**

Knowledge bank specific operations:

- `getKnowledgeDocuments()` - Get all approved documents
- `searchKnowledge(query)` - Search knowledge base
- `getKnowledgeByCategory(category)` - Filter by category
- `getRelatedDocuments(id, limit)` - Get related documents
- `getCategoryStats()` - Category statistics
- `getRecentDocuments(limit)` - Recent documents
- `exportDocumentAsPDF(id)` - Export as PDF

### 4. **activityService.ts**

Activity feed management:

- `getRecentActivities(limit)` - Get recent activities
- `getDocumentActivities(documentId)` - Document activities
- `getUserActivities(userName)` - User activities
- `addActivity(activity)` - Add new activity

---

## 💡 Usage Examples

### Import Services

```typescript
// Import all services
import { documentService, authService, knowledgeService, activityService } from '@/services';

// Or import individual services
import { documentService } from '@/services/documentService';
```

### Using Document Service

```typescript
// Get all documents
const documents = await documentService.getAllDocuments();

// Upload new document
const newDoc = await documentService.uploadDocument({
  title: "Safety Procedure",
  fileName: "safety.pdf",
  category: "Sikkerhet",
  uploadedBy: "John Doe",
  originalContent: "...",
  revisedContent: "..."
});

// Approve document
await documentService.approveDocument(documentId);
```

### Using Auth Service

```typescript
// Login
const authResponse = await authService.login({
  email: "admin@glencore.com",
  password: "admin123"
});

// Check if authenticated
if (authService.isAuthenticated()) {
  const user = authService.getCurrentUser();
}

// Logout
await authService.logout();
```

### Using Knowledge Service

```typescript
// Search knowledge base
const results = await knowledgeService.searchKnowledge("sikkerhet");

// Get related documents
const related = await knowledgeService.getRelatedDocuments(docId, 5);

// Get category statistics
const stats = await knowledgeService.getCategoryStats();
```

---

## 🔄 Migration to Backend

Each service method has commented-out code showing the future backend implementation:

```typescript
// Current (Mock):
async getAllDocuments(): Promise<Document[]> {
  await this.simulateDelay(300);
  return [...mockDocuments];
}

// Future (Real API):
async getAllDocuments(): Promise<Document[]> {
  const response = await fetch('/api/documents', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  return await response.json();
}
```

### Migration Steps:

1. ✅ Set up backend API endpoints
2. ✅ Replace mock implementation with fetch calls
3. ✅ Add proper error handling
4. ✅ Add loading states in components
5. ✅ Test with real backend

---

## 🎯 Benefits

✅ **Separation of Concerns** - UI separated from business logic  
✅ **Easy Testing** - Services can be mocked/tested independently  
✅ **Type Safety** - Full TypeScript support  
✅ **Reusability** - Services used across multiple components  
✅ **Backend Ready** - Clear migration path to real API  
✅ **Maintainability** - Changes in one place affect all usages  

---

## 📦 Related Files

- **Types**: `/src/types/` - TypeScript interfaces
- **Mock Data**: `/src/data/mock-documents.ts` - Development data
- **Context**: `/src/app/context/` - React Context for state management

---

## 🔐 Authentication Flow

```
1. User enters credentials
2. authService.login(credentials)
3. Service validates (mock) or calls API (future)
4. Token + User saved to localStorage
5. authService.isAuthenticated() returns true
6. Protected routes accessible
```

---

## 📊 Data Flow

```
Component → Service → Mock Data (now) / API (future) → Service → Component
```

---

## 🚀 Next Steps

1. Connect components to services (replace context direct access)
2. Add loading states to UI
3. Add error handling
4. Implement backend API
5. Update service implementations
6. Remove mock data imports
