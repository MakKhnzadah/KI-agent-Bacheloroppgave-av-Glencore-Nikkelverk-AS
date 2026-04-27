import { createBrowserRouter } from "react-router";
import { LoginPage } from "./pages/login-page";
import { DashboardPage } from "./pages/dashboard-page";
import { FilesPage } from "./pages/files-page.tsx";
import { UploadPage } from "./pages/upload-page";
import { QueuePage } from "./pages/queue-page";
import { KnowledgeBankPage } from "./pages/knowledge-bank-page";
import { DocumentDetailPage } from "./pages/document-detail-page";
import { ErrorBoundary } from "./components/error-boundary";
import { ProtectedRoute } from "./components/protected-route";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: LoginPage,
    ErrorBoundary: ErrorBoundary,
  },
  {
    path: "/dashboard",
    element: (
      <ProtectedRoute allowedRoles={["employee", "expert", "admin"]}>
        <DashboardPage />
      </ProtectedRoute>
    ),
    ErrorBoundary: ErrorBoundary,
  },
  {
    path: "/upload",
    element: (
      <ProtectedRoute allowedRoles={["expert", "admin"]}>
        <UploadPage />
      </ProtectedRoute>
    ),
    ErrorBoundary: ErrorBoundary,
  },
  {
    path: "/queue",
    element: (
      <ProtectedRoute allowedRoles={["expert", "admin"]}>
        <QueuePage />
      </ProtectedRoute>
    ),
    ErrorBoundary: ErrorBoundary,
  },
  {
    path: "/review-queue",
    element: (
      <ProtectedRoute allowedRoles={["expert", "admin"]}>
        <QueuePage />
      </ProtectedRoute>
    ),
    ErrorBoundary: ErrorBoundary,
  },
  {
    path: "/knowledge-bank",
    element: (
      <ProtectedRoute allowedRoles={["employee", "expert", "admin"]}>
        <KnowledgeBankPage />
      </ProtectedRoute>
    ),
    ErrorBoundary: ErrorBoundary,
  },
  {
    path: "/files",
    element: (
      <ProtectedRoute allowedRoles={["employee", "expert", "admin"]}>
        <FilesPage />
      </ProtectedRoute>
    ),
    ErrorBoundary: ErrorBoundary,
  },
  {
    path: "/document/:id",
    element: (
      <ProtectedRoute allowedRoles={["employee", "expert", "admin"]}>
        <DocumentDetailPage />
      </ProtectedRoute>
    ),
    ErrorBoundary: ErrorBoundary,
  },
]);