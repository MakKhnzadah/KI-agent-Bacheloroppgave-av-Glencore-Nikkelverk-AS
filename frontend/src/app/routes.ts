import { createBrowserRouter } from "react-router";
import { LoginPage } from "@/app/pages/login-page";
import { DashboardPage } from "@/app/pages/dashboard-page";
import { UploadPage } from "@/app/pages/upload-page";
import { QueuePage } from "@/app/pages/queue-page";
import { KnowledgeBankPage } from "@/app/pages/knowledge-bank-page";
import { DocumentDetailPage } from "@/app/pages/document-detail-page";
import { VectorDbPage } from "@/app/pages/vector-db-page";
import { ErrorBoundary } from "@/app/components/error-boundary";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: LoginPage,
    ErrorBoundary: ErrorBoundary,
  },
  {
    path: "/dashboard",
    Component: DashboardPage,
    ErrorBoundary: ErrorBoundary,
  },
  {
    path: "/upload",
    Component: UploadPage,
    ErrorBoundary: ErrorBoundary,
  },
  {
    path: "/queue",
    Component: QueuePage,
    ErrorBoundary: ErrorBoundary,
  },
  {
    path: "/review-queue",
    Component: QueuePage,
    ErrorBoundary: ErrorBoundary,
  },
  {
    path: "/knowledge-bank",
    Component: KnowledgeBankPage,
    ErrorBoundary: ErrorBoundary,
  },
  {
    path: "/files",
    Component: VectorDbPage,
    ErrorBoundary: ErrorBoundary,
  },
  {
    path: "/document/:id",
    Component: DocumentDetailPage,
    ErrorBoundary: ErrorBoundary,
  },
]);