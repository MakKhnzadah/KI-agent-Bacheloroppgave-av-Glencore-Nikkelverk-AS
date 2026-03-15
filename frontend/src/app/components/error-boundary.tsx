import { useRouteError, useNavigate } from "react-router";

export function ErrorBoundary() {
  const error = useRouteError() as any;
  const navigate = useNavigate();

  return (
    <div className="flex items-center justify-center h-screen bg-[#E6F7F7]">
      <div className="bg-white rounded-lg p-8 max-w-md text-center">
        <h1 className="text-2xl font-semibold text-[#000000] mb-4">Noe gikk galt</h1>
        <p className="text-sm text-[#000000] mb-6">
          {error?.statusText || error?.message || "En uventet feil oppstod"}
        </p>
        <button
          onClick={() => navigate("/dashboard")}
          className="px-6 py-2 bg-[#00AFAA] hover:bg-[#00AFAA]/90 text-white rounded-md transition-colors text-sm font-semibold"
        >
          Tilbake til Dashboard
        </button>
      </div>
    </div>
  );
}