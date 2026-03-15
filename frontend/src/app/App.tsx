import { RouterProvider } from "react-router";
import { router } from "@/app/routes";
import { AuthProvider } from "@/app/context/auth-context";
import { DocumentsProvider } from "@/app/context/documents-context";

export default function App() {
  return (
    <AuthProvider>
      <DocumentsProvider>
        <RouterProvider router={router} />
      </DocumentsProvider>
    </AuthProvider>
  );
}