import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type DragEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { FileDown } from "lucide-react";
import { api, downloadBlob } from "../api/client";
import type { Case, Doc, Evidence, Finding, ProcessResult } from "../api/types";
import { DOC_TYPE_LABEL, inr } from "../api/types";
import { useToast } from "../components/ui";
import { Stepper } from "../components/Progress";

type Role = "salary_slip" | "bank_statement";
interface Result { caseItem: Case; docs: Doc[]; finding: Finding | null; process: ProcessResult; all: Finding[] }
const SAMPLES = [[1, "Consistent documents"], [2, "Salary vs bank mismatch"], [3, "Duplicate invoice, altered amount"], [4, "Broken running balance"], [5, "Multiple conflicts"]] as const;

function PageGlyph({ role }: { role: Role }) {
  return (
    <div aria-hidden className="relative h-12 w-9 shrink-0 rounded-sm border border-ink-800 bg-white dark:border-ink-200 dark:bg-side">
      <div className="absolute right-0 top-0 h-2.5 w-2.5 border-b border-l border-ink-800 bg-fog dark:border-ink-200 dark:bg-surface" />
      {role === "salary_slip" ? (
        <>
          <div className="absolute left-1.5 top-4 h-px w-4 bg-surface dark:bg-ink-200" />
          <div className="absolute left-1.5 top-6 h-px w-3 bg-surface dark:bg-ink-200" />
          <div className="absolute bottom-1 right-1.5 font-mono text-[9px] leading-none text-ink-800 dark:text-fg2">₹</div>
        </>
      ) : (
        <>{[3.5, 5, 6.5, 8, 9.5].map((t, i) => <div key={t} className="absolute left-1.5 h-px bg-surface dark:bg-ink-200" style={{ top: `${t * 4}px`, width: i % 2 ? "14px" : "22px" }} />)}</>
      )}
    </div>
  );
}

function DocumentPanel({ role, label, description, file, onFile, busy, doc }: {
  role: Role; label: string; description: string; file: File | null; onFile: (f: File) => void; busy: boolean; doc?: Doc;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const id = `file-${role}`;
  const onDrop = (e: DragEvent) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f && !busy) onFile(f); };
  const misread = doc && doc.status === "processed" && doc.doc_type !== role;
  return (
    <div onDragOver={(e) => { e.preventDefault(); if (!busy) setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={onDrop}
      className={`card flex gap-4 p-5 transition-colors ${drag ? "border-accent-500" : file ? "border-ink-800 dark:border-ink-300" : ""}`}>
      <PageGlyph role={role} />
      <div className="min-w-0 flex-1">
        <div className="eyebrow">{role === "salary_slip" ? "Document one" : "Document two"}</div>
        <h3 className="mt-0.5 font-semibold">{label}</h3>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{description}</p>
        <label htmlFor={id} className="sr-only">Choose the {label.toLowerCase()} file</label>
        <input id={id} ref={inputRef} type="file" accept=".pdf,.png,.jpg,.jpeg" className="sr-only" disabled={busy}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }} />
        {file ? (
          <div className="mt-4 flex items-center justify-between gap-3 border-t border-slate-200 pt-3 dark:border-line">
            <div className="min-w-0">
              <div className="truncate text-sm font-medium">{file.name}</div>
              <div className="text-xs text-slate-500">
                {(file.size / 1024).toFixed(0)} KB
                {doc ? (doc.status === "processed" ? `, read as ${DOC_TYPE_LABEL[doc.doc_type] ?? doc.doc_type}` : `, ${doc.status}`) : busy ? "" : ", ready"}
              </div>
              {misread && <div className="mt-1 text-xs text-amber-700">This file was classified as a {DOC_TYPE_LABEL[doc!.doc_type] ?? doc!.doc_type}, not a {label.toLowerCase()}.</div>}
              {doc?.error_message && <div className="mt-1 text-xs text-slate-600">{doc.error_message}</div>}
            </div>
            <button type="button" className="btn-secondary shrink-0" disabled={busy} onClick={() => inputRef.current?.click()}>Replace</button>
          </div>
        ) : (
          <button type="button" disabled={busy} onClick={() => inputRef.current?.click()}
            className="mt-4 w-full rounded-lg border border-dashed border-slate-300 px-4 py-5 text-sm text-slate-600 transition-colors hover:border-accent-500 hover:text-accent-700 dark:border-ink-600 dark:text-slate-400">
            Drop the file here or choose a file
          </button>
        )}
      </div>
    </div>
  );
}

function AmountCell({ heading, field, value, ev, doc }: { heading: string; field: string; value: number | null; ev?: Evidence; doc?: Doc }) {
  const failed = doc && doc.status !== "processed";
  return (
    <div className="bg-white px-5 py-4 dark:bg-surface">
      <div className="eyebrow">{heading}</div>
      <div className="text-xs text-slate-500">{field}</div>
      {value !== null ? <div className="amount mt-2 text-2xl font-medium">{inr(value)}</div>
        : <div className="mt-2 text-lg text-slate-500">{failed ? "Document not read" : "Not extracted"}</div>}
      <dl className="mt-3 space-y-0.5 text-xs text-slate-600 dark:text-slate-400">
        {doc && <div className="flex gap-2"><dt className="w-14 shrink-0 text-slate-400">Source</dt><dd className="truncate">{doc.original_filename}</dd></div>}
        {ev && <div className="flex gap-2"><dt className="w-14 shrink-0 text-slate-400">Field</dt><dd className="font-mono">{ev.field}{ev.page ? <Link className="link ml-2 font-sans" to={`/cases/${doc?.case_id}/documents/${ev.document_id}?page=${ev.page}&field=${encodeURIComponent(ev.field)}`}>page {ev.page}</Link> : null}</dd></div>}
        {ev?.date && <div className="flex gap-2"><dt className="w-14 shrink-0 text-slate-400">Credit</dt><dd className="truncate">{ev.date}{ev.description ? `, ${ev.description}` : ""}</dd></div>}
        {failed && doc?.error_message && <div className="text-slate-500">{doc.error_message}</div>}
      </dl>
    </div>
  );
}

function ResultSection({ r, onReport, reportBusy }: { r: Result; onReport: () => void; reportBusy: boolean }) {
  const f = r.finding;
  const outcome = r.caseItem.risk_outcome;
  const toneClass = outcome.startsWith("Low") ? "text-emerald-700 dark:text-emerald-300" : outcome.startsWith("Insufficient") || outcome.startsWith("Processing") ? "text-slate-600 dark:text-slate-300" : "text-amber-700 dark:text-amber-300";
  const slipDoc = r.docs.find((d) => d.doc_type === "salary_slip") ?? r.docs[0];
  const bankDoc = r.docs.find((d) => d.doc_type === "bank_statement") ?? r.docs[1];
  const slipEv = f?.evidence.find((e) => e.doc_type === "salary_slip" && e.field === "net_pay");
  const bankEv = f?.evidence.find((e) => e.doc_type === "bank_statement" && e.field.includes("credit"));
  const slipAmt = slipEv?.value ? Number(slipEv.value) : null;
  const bankAmt = bankEv?.value ? Number(bankEv.value) : null;
  const diff = slipAmt !== null && bankAmt !== null ? Math.abs(slipAmt - bankAmt) : null;
  const others = r.all.filter((x) => x.rule_id !== "cross_document.salary_vs_bank" && x.severity !== "info");
  return (
    <section aria-live="polite" className="card mt-8 animate-fade p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div><div className="eyebrow">Finding</div><h2 className={`mt-1 text-2xl font-semibold ${toneClass}`}>{outcome}</h2></div>
        <div className="flex gap-2">
          <button className="btn-primary" onClick={onReport} disabled={reportBusy}><FileDown className="h-4 w-4" />{reportBusy ? "Preparing report…" : "Download report"}</button>
          <Link className="btn-secondary" to={`/cases/${r.caseItem.id}/summary`}>Open the case</Link>
        </div>
      </div>
      <div className="mt-6 grid gap-px overflow-hidden rounded-lg border border-slate-200 bg-slate-200 dark:border-line dark:bg-ink-700 md:grid-cols-[1fr_auto_1fr]">
        <AmountCell heading="Salary slip" field="Net pay stated on the slip" value={slipAmt} ev={slipEv} doc={slipDoc} />
        <div className="flex flex-col justify-center bg-white px-6 py-4 text-center dark:bg-surface">
          <div className="eyebrow">Difference</div>
          <div className={`amount mt-2 text-2xl font-medium ${diff === null ? "text-slate-400" : diff > 0 ? "text-amber-700 dark:text-amber-300" : ""}`}>{diff === null ? "—" : inr(diff)}</div>
          {diff !== null && <div className="mt-1 text-xs text-slate-500">{diff > 0 ? "between slip and credit" : "the amounts agree"}</div>}
        </div>
        <AmountCell heading="Bank statement" field="Salary credit found in the statement" value={bankAmt} ev={bankEv} doc={bankDoc} />
      </div>
      <div className="mt-4 max-w-3xl text-sm text-slate-700 dark:text-slate-300">
        {f ? <>{f.explanation || f.title}{f.possible_extraction_error && " Extraction confidence on an involved field is low, so this is weighted as a possible extraction error."}</>
          : "The salary comparison could not be evaluated: one of the files was not read as a salary slip or a bank statement, so there is no evidence to compare."}
        {outcome.startsWith("Low") && " Agreement between these two documents does not establish that either document is authentic."}
      </div>
      {others.length > 0 && <p className="mt-3 text-sm text-slate-600 dark:text-slate-400">{others.length} other finding{others.length === 1 ? "" : "s"} from the single-document and identity checks: <Link className="link" to={`/cases/${r.caseItem.id}/summary`}>see the case summary</Link>.</p>}
    </section>
  );
}

export default function Investigate() {
  const toast = useToast();
  const qc = useQueryClient();
  const nav = useNavigate();
  const [slip, setSlip] = useState<File | null>(null);
  const [stmt, setStmt] = useState<File | null>(null);
  const [password, setPassword] = useState("");
  const [phase, setPhase] = useState<"uploading" | "processing" | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const run = useMutation({
    mutationFn: async (): Promise<Result> => {
      setPhase("uploading");
      const c = await api<Case>("/cases", { method: "POST", json: { title: `Salary verification, ${new Date().toLocaleString()}`, case_type: "loan_investigation", description: "Created from the Investigate workspace: salary slip against bank statement." } });
      const fd = new FormData();
      fd.append("files", slip!);
      fd.append("files", stmt!);
      if (password) fd.append("password", password);
      await api<Doc[]>(`/cases/${c.id}/documents`, { method: "POST", body: fd });
      setPhase("processing");
      const process = await api<ProcessResult>(`/cases/${c.id}/process`, { method: "POST" });
      const [caseItem, docs, all] = await Promise.all([api<Case>(`/cases/${c.id}`), api<Doc[]>(`/cases/${c.id}/documents`), api<Finding[]>(`/cases/${c.id}/findings`)]);
      return { caseItem, docs, finding: all.find((x) => x.rule_id === "cross_document.salary_vs_bank") ?? null, process, all };
    },
    onSuccess: (r) => { setResult(r); qc.invalidateQueries({ queryKey: ["cases"] }); },
    onError: (e: Error) => toast.push(e.message, "error"),
    onSettled: () => setPhase(null),
  });
  const sample = useMutation({
    mutationFn: (sid: number) => api<Case>(`/demo/scenarios/${sid}`, { method: "POST" }),
    onSuccess: (c) => { qc.invalidateQueries({ queryKey: ["cases"] }); nav(`/cases/${c.id}/summary`); },
    onError: (e: Error) => toast.push(e.message, "error"),
  });
  const report = useMutation({
    mutationFn: async () => downloadBlob(await api<Blob>(`/cases/${result!.caseItem.id}/report.pdf`), `docsentry_case_${result!.caseItem.id}.pdf`),
    onError: (e: Error) => toast.push(e.message, "error"),
  });
  const busy = run.isPending;
  const docFor = (file: File | null) => result && file ? result.docs.find((d) => d.original_filename === file.name.replace(/[^A-Za-z0-9._-]/g, "_")) : undefined;
  return (
    <div className="max-w-5xl">
      <h1 className="text-3xl font-semibold leading-tight">Verify what the documents say.</h1>
      <p className="mt-2 max-w-2xl text-slate-600 dark:text-slate-400">
        Upload a salary slip and the bank statement for the same month. DocSentry reads the net pay from the slip, finds the salary credit in the statement and reports whether they agree, with every amount tied to the page it came from.
      </p>
      <div className="mt-8 grid gap-4 md:grid-cols-2">
        <DocumentPanel role="salary_slip" label="Salary slip" description="The net pay stated here is examined." file={slip} onFile={(f) => { setSlip(f); setResult(null); }} busy={busy} doc={docFor(slip)} />
        <DocumentPanel role="bank_statement" label="Bank statement" description="The salary credit for the slip's month is examined." file={stmt} onFile={(f) => { setStmt(f); setResult(null); }} busy={busy} doc={docFor(stmt)} />
      </div>
      <div className="mt-5 flex flex-wrap items-end gap-4">
        <div className="w-full sm:w-64">
          <label className="label" htmlFor="pdf-password">Statement password, if protected</label>
          <input id="pdf-password" className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="off" disabled={busy} />
        </div>
        <button className="btn-primary px-5 py-2.5 text-base" disabled={!slip || !stmt || busy} onClick={() => run.mutate()}>
          {busy ? (phase === "uploading" ? "Uploading…" : "Investigating…") : "Investigate"}
        </button>
        <p className="text-xs text-slate-500">The password is used in memory to open the file and is never stored.</p>
      </div>
      {busy && (
        <div className="mt-5" role="status">
          <Stepper steps={[{ label: "Upload", state: phase === "uploading" ? "active" : "done" }, { label: "Extract", state: phase === "processing" ? "active" : "idle" }, { label: "Compare", state: phase === "processing" ? "active" : "idle" }, { label: "Score", state: "idle" }]} />
        </div>
      )}
      {result && <ResultSection r={result} onReport={() => report.mutate()} reportBusy={report.isPending} />}
      <div className="mt-10 rounded-xl border border-dashed border-slate-300 p-5 dark:border-ink-600">
        <div className="flex flex-wrap items-center gap-3">
          <div className="mr-2"><div className="font-medium">Or try a sample case</div><div className="text-xs text-slate-500">Generates synthetic documents and runs the real pipeline. Nothing is pre-computed.</div></div>
          {SAMPLES.map(([sid, label]) => <button key={sid} className="chip" disabled={sample.isPending} onClick={() => sample.mutate(sid)}>{sample.isPending && sample.variables === sid ? "Running…" : label}</button>)}
        </div>
      </div>
    </div>
  );
}