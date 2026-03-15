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
├── data/                 # Mock Data Layer
│   └── mock-documents.ts # Development seed data
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
Decouples business logic from the UI. Components call these services for data operations, making it easy to swap mock data for a real backend API in the future without changing the UI code.

### 3. Data Layer (`/src/data/`)
Contains mock JSON/TypeScript data used for development. This allows frontend development to proceed independently of backend progress.

---

## 🔄 Data Flow

The app uses a **Service-Context** pattern:
1. **Pages** interact with **Context** hooks (e.g., `useDocuments`).
2. **Context** providers call **Services** to perform actions.
3. **Services** currently fetch from **Mock Data** but are ready to be updated with `fetch()` calls to a real API.

---

## 🚀 Backend Integration

The system is designed for a seamless backend transition:
- **Phase 1 (Current)**: Services return hardcoded data wrapped in Promises to simulate network latency.
- **Phase 2 (Migration)**: Replace service logic with real `fetch` or `axios` calls to `/api/` endpoints.
- **Phase 3 (Final)**: Remove the `/src/data` folder and switch to live database storage.

---

## 🎨 Design System

- **Colors**:
  - Primary Teal: `#00AFAA`
  - Teal Background: `#00afaa1a` (10% opacity)
  - Layout Gray: `#ededed`
- **Typography**: Montserrat (300/400/600 weights)
- **Standards**: Header height is fixed at `103px` and UI cards use a consistent `10px/14px` border radius.

---

**Last Updated**: March 15, 2026  
**Version**: 1.1.0  
**Status**: ✅ Production Ready (Mock)
