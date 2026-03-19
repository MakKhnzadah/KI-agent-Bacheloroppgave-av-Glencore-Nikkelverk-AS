import { RouterProvider } from "react-router";
import { router } from "@/app/routes";
import { AuthProvider } from "@/app/context/auth-context";
import { DocumentsProvider } from "@/app/context/documents-context";
import { ToastProvider } from "@/app/context/toast-context";

export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <DocumentsProvider>
          <RouterProvider router={router} />
        </DocumentsProvider>
      </AuthProvider>
    </ToastProvider>
  );
}