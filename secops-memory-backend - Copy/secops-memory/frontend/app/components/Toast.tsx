"use client";

import { createContext, useCallback, useContext, useState } from "react";

type ToastKind = "success" | "error" | "info";
type ToastItem = { id: number; kind: ToastKind; text: string };

const Ctx = createContext<(kind: ToastKind, text: string) => void>(() => {});
export const useToast = () => useContext(Ctx);

const styles: Record<ToastKind, string> = {
  success: "border-emerald-500/40 bg-emerald-950/80 text-emerald-200",
  error: "border-red-500/40 bg-red-950/80 text-red-200",
  info: "border-cyan-500/40 bg-cyan-950/80 text-cyan-200",
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const push = useCallback((kind: ToastKind, text: string) => {
    const id = Date.now() + Math.random();
    setItems((cur) => [...cur, { id, kind, text }]);
    setTimeout(() => setItems((cur) => cur.filter((t) => t.id !== id)), 4500);
  }, []);

  return (
    <Ctx.Provider value={push}>
      {children}
      <div aria-live="polite" aria-atomic="false" className="pointer-events-none fixed right-4 top-4 z-50 flex w-[min(22rem,calc(100vw-2rem))] flex-col gap-2">
        {items.map((t) => (
          <div
            key={t.id}
            role={t.kind === "error" ? "alert" : "status"}
            className={`toast-in pointer-events-auto rounded-xl border px-4 py-3 text-sm shadow-xl backdrop-blur ${styles[t.kind]}`}
          >
            {t.text}
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
