import { createContext, useCallback, useContext, useMemo, useState, ReactNode } from "react";

type ToastTone = "error" | "success";

interface ToastItem {
  id: number;
  message: string;
  tone: ToastTone;
}

interface ToastContextType {
  showToast: (message: string, tone?: ToastTone, durationMs?: number) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const showToast = useCallback((message: string, tone: ToastTone = "error", durationMs: number = 4500) => {
    const id = Date.now() + Math.floor(Math.random() * 1000);

    setToasts((prev) => [...prev, { id, message, tone }]);

    window.setTimeout(() => {
      setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, durationMs);
  }, []);

  const value = useMemo(() => ({ showToast }), [showToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="fixed top-4 right-4 z-[1000] flex w-[min(420px,calc(100vw-2rem))] flex-col gap-2">
        {toasts.map((toast) => {
          const toneClasses =
            toast.tone === "success"
              ? "border-[#0B6A46] bg-[#E8F6EF] text-[#0B6A46]"
              : "border-[#B3232F] bg-[#FCEBEC] text-[#7C0D15]";

          return (
            <div key={toast.id} className={`rounded-md border px-4 py-3 text-sm shadow ${toneClasses}`} role="status">
              {toast.message}
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within ToastProvider");
  }

  return context;
}
