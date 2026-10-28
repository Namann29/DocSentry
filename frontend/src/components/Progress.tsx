import { useEffect, useState } from "react";
import { Check } from "lucide-react";

export const TONE_STROKE: Record<string, string> = { ok: "var(--sev-ok-hex)", medium: "var(--sev-warn-hex)", high: "var(--sev-high-hex)", info: "var(--muted-hex)", warn: "var(--sev-warn-hex)" };

export function ScoreRing({ score, tone, size = 132 }: { score: number; tone: string; size?: number }) {
  const r = (size - 14) / 2;
  const c = 2 * Math.PI * r;
  const [offset, setOffset] = useState(c);
  useEffect(() => { const t = setTimeout(() => setOffset(c - (Math.min(100, Math.max(0, score)) / 100) * c), 60); return () => clearTimeout(t); }, [score, c]);
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`Risk score ${score} of 100`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="currentColor" className="text-slate-200 dark:text-ink-700" strokeWidth="10" />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={TONE_STROKE[tone] ?? TONE_STROKE.info} strokeWidth="10" strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={offset} transform={`rotate(-90 ${size / 2} ${size / 2})`} style={{ transition: "stroke-dashoffset 900ms cubic-bezier(.2,.8,.2,1)" }} />
      <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle" className="fill-fg" style={{ fontSize: size * 0.26, fontWeight: 600 }}>{score}</text>
      <text x="50%" y="68%" dominantBaseline="central" textAnchor="middle" className="fill-muted" style={{ fontSize: size * 0.085 }}>of 100</text>
    </svg>
  );
}

export type StepState = "done" | "active" | "idle" | "failed";
export function Stepper({ steps }: { steps: { label: string; hint?: string; state: StepState }[] }) {
  return (
    <ol className="flex flex-wrap gap-x-2 gap-y-3">
      {steps.map((s, i) => (
        <li key={s.label} className="flex items-center gap-2">
          <span className={`flex h-6 w-6 items-center justify-center rounded-full border text-[11px] font-semibold ${s.state === "done" ? "border-emerald-600 bg-emerald-600 text-white" : s.state === "active" ? "border-accent-600 text-accent-700" : s.state === "failed" ? "border-red-600 text-red-600" : "border-slate-300 text-slate-400"}`}>
            {s.state === "done" ? <Check className="h-3.5 w-3.5" /> : s.state === "active" ? <span className="h-2 w-2 animate-pulseDot rounded-full bg-accent-600" /> : i + 1}
          </span>
          <span className={`text-sm ${s.state === "idle" ? "text-slate-400" : "font-medium"}`}>{s.label}{s.hint && <span className="ml-1 font-normal text-slate-500">{s.hint}</span>}</span>
          {i < steps.length - 1 && <span className="mx-1 hidden h-px w-8 bg-slate-300 sm:block dark:bg-ink-600" />}
        </li>
      ))}
    </ol>
  );
}