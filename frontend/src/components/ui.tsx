import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4 border-b border-slate-200 pb-4 dark:border-ink-700">
      <div className="max-w-2xl">
        <h1 className="text-[28px] font-semibold leading-tight">{title}</h1>
        {subtitle && <p className="mt-2 text-[15px] leading-relaxed text-fg2">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Card({ title, actions, children, className = "" }: { title?: string; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-2.5 dark:border-ink-700">
          <h2 className="text-[17px] font-semibold">{title}</h2>
          {actions}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

const DOT: Record<string, string> = {
  high: "bg-red-600", medium: "bg-amber-500", low: "bg-yellow-400", info: "bg-slate-400", ok: "bg-emerald-600", warn: "bg-orange-500", neutral: "bg-ink-500",
};
const TEXT: Record<string, string> = {
  high: "text-red-700 dark:text-red-300", medium: "text-amber-700 dark:text-amber-300", low: "text-yellow-700 dark:text-yellow-300",
  info: "text-slate-600 dark:text-slate-300", ok: "text-emerald-700 dark:text-emerald-300", warn: "text-orange-700 dark:text-orange-300", neutral: "text-ink-700 dark:text-ink-100",
};
export function Badge({ tone = "neutral", children, title }: { tone?: string; children: ReactNode; title?: string }) {
  return (
    <span title={title} className={`inline-flex items-center gap-1.5 whitespace-nowrap text-[13px] font-medium ${TEXT[tone] ?? TEXT.neutral}`}>
      <span className={`inline-block h-1.5 w-1.5 rounded-full ${DOT[tone] ?? DOT.neutral}`} />{children}
    </span>
  );
}

export const outcomeTone = (o: string) =>
  o.startsWith("High") ? "high" : o.startsWith("Review") ? "medium" : o.startsWith("Low") ? "ok" : o.startsWith("Processing") ? "warn" : "info";
export const statusTone = (s: string) => (s === "processed" ? "ok" : s === "failed" ? "high" : s === "unsupported" ? "warn" : "info");

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="border-l-2 border-slate-200 pl-3 dark:border-ink-600">
      <div className="text-[13px] text-fg2">{label}</div>
      <div className="mt-1 text-[32px] font-semibold tabular-nums leading-tight">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-slate-500">{hint}</div>}
    </div>
  );
}

export function Empty({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="rounded border border-dashed border-slate-300 px-6 py-10 text-center dark:border-ink-600">
      <div className="text-sm font-medium">{title}</div>
      {hint && <div className="mx-auto mt-1 max-w-md text-sm text-slate-500">{hint}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Skeleton({ rows = 4 }: { rows?: number }) {
  return <div className="space-y-2">{Array.from({ length: rows }).map((_, i) => <div key={i} className="h-4 animate-pulse rounded bg-slate-200 dark:bg-ink-700" style={{ width: `${88 - (i % 3) * 14}%` }} />)}</div>;
}

export function ErrorBox({ error }: { error: unknown }) {
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <div className="flex items-start gap-2 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><span>{msg}</span>
    </div>
  );
}

export function Unavailable({ feature, reason }: { feature: string; reason: string }) {
  return (
    <div className="border-l-2 border-amber-500 bg-amber-50 px-4 py-3 text-sm dark:bg-amber-950/30">
      <div className="font-medium">{feature} is not available in this build</div>
      <div className="mt-1 text-slate-700 dark:text-slate-300">{reason}</div>
    </div>
  );
}

interface Toast { id: number; message: string; tone: "ok" | "error" | "info" }
const ToastCtx = createContext<{ push: (message: string, tone?: Toast["tone"]) => void }>({ push: () => {} });
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((message: string, tone: Toast["tone"] = "info") => {
    const id = Date.now() + Math.random();
    setItems((s) => [...s, { id, message, tone }]);
    setTimeout(() => setItems((s) => s.filter((t) => t.id !== id)), 6000);
  }, []);
  return (
    <ToastCtx.Provider value={{ push }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 space-y-2" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`flex max-w-sm items-start gap-2 rounded border-l-2 bg-white px-3 py-2 text-sm shadow-md dark:bg-ink-800 ${t.tone === "ok" ? "border-emerald-600" : t.tone === "error" ? "border-red-600" : "border-ink-500"}`}>
            {t.tone === "ok" ? <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" /> : t.tone === "error" ? <AlertTriangle className="mt-0.5 h-4 w-4 text-red-600" /> : <Info className="mt-0.5 h-4 w-4 text-ink-500" />}
            <span className="flex-1">{t.message}</span>
            <button onClick={() => setItems((s) => s.filter((x) => x.id !== t.id))} aria-label="Dismiss"><X className="h-4 w-4 text-slate-400" /></button>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}