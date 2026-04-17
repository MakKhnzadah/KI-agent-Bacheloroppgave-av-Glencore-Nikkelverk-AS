# 🏗️ Glencore Knowledge Base - Architecture

## 📋 Project Overview

The **Glencore Knowledge Base** is an intelligent management system designed for Glencore Nikkelverk AS. It provides a modern interface for uploading, reviewing, and browsing technical documentation and activity logs.

- **Stack**: React 18 + TypeScript + Tailwind CSS v4
- **Routing**: React Router 7 (Data Mode)
- **Branding**: Official Glencore Teal (#00AFAA) & Montserrat Typography

---

## 📁 Project Structure

```
src/
├── app/                  # Application Layer
│   ├── components/      # UI components (sidebar, error boundaries)
│   ├── context/         # Global state management
│   ├── pages/           # View components (Login, Dashboard, etc.)
│   └── routes.ts        # Route definitions
├── types/                # Type Safety Layer
│   └── document.ts      # TypeScript interfaces for data
├── services/             # Business Logic Layer
│   └── documentService.ts # API and data processing logic
└── styles/               # Styling Layer
    ├── theme.css        # Design tokens
    └── tailwind.css     # Framework imports
```

---

## 🎯 System Features

| Page | Description | Status |
|------|-------------|--------|
| **Login** | Secure authentication portal | ✅ Complete |
| **Dashboard** | Activity overview and system statistics | ✅ Complete |
| **Upload** | Drag-and-drop document ingestion | ✅ Complete |
| **Queue** | Review workflow for pending documents | ✅ Complete |
| **Knowledge Bank** | Searchable database of approved files | ✅ Complete |
| **Document Detail** | Full-screen document analysis and metadata | ✅ Complete |

---

## 🔧 Architecture Components

### 1. Types Layer (`/src/types/`)
Provides central type definitions (`Document`, `User`, `Activity`) used throughout the app. This ensures strict type safety and better developer experience through IDE IntelliSense.

### 2. Services Layer (`/src/services/`)
Decouples business logic from the UI. Components call these services for data operations via real backend API endpoints.

---

## 🔄 Data Flow

The app uses a **Service-Context** pattern:
1. **Pages** interact with **Context** hooks (e.g., `useDocuments`).
2. **Context** providers call **Services** to perform actions.
3. **Services** call backend endpoints (`/workflow`, `/api/auth`, `/api/activities`) and return typed data to UI state.

---

## 🚀 Backend Integration

The frontend is integrated with FastAPI endpoints for authentication, document workflow, vector search, and activity feed.

---

## 🎨 Design System

- **Colors**:
  - Primary Teal: `#00AFAA`
  - Teal Background: `#00afaa1a` (10% opacity)
  - Layout Gray: `#ededed`
- **Typography**: Montserrat (300/400/600 weights)
- **Standards**: Header height is fixed at `103px` and UI cards use a consistent `10px/14px` border radius.

---

**Last Updated**: April 17, 2026  
**Version**: 1.1.0  
**Status**: ✅ Production Ready (API-integrated)
