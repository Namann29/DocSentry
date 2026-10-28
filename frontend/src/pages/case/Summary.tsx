import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { FileDown, Play } from "lucide-react";
import { api, downloadBlob } from "../../api/client";
import { useCase, useDocuments, useFindings, useRisk } from "../../api/hooks";
import type { Finding, ProcessResult } from "../../api/types";
import { DOC_TYPE_LABEL, LEVEL_NAMES } from "../../api/types";
import { Badge, Empty, ErrorBox, Skeleton, outcomeTone, statusTone, useToast } from "../../components/ui";
import { ScoreRing, Stepper } from "../../components/Progress";
import { Explain } from "../../components/Explain";

const RANK = { high: 0, medium: 1, low: 2, info: 3 } as const;

function Discrepancy({ f }: { f: Finding }) {
  const amounts = f.evidence.filter((e) => e.value && /^-?\d+(\.\d+)?$/.test(e.value));
  return (
    <li className="flex gap-4 py-3">
      <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${f.severity === "high" ? "bg-red-500" : f.severity === "medium" ? "bg-amber-500" : "bg-yellow-400"}`} />
      <div className="min-w-0 flex-1">
        <div className="font-medium leading-snug">{f.title}</div>
        <div className="mt-0.5 text-xs text-slate-500">{LEVEL_NAMES[f.level]}{f.possible_extraction_error ? ", possible extraction error" : ""}</div>
        {amounts.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {amounts.slice(0, 3).map((e, i) => (
              <Link key={i} to={`../documents/${e.document_id}${e.page ? `?page=${e.page}&field=${encodeURIComponent(e.field)}` : ""}`}
                className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs hover:border-accent-400 dark:border-ink-600 dark:bg-ink-700">
                <span className="text-slate-500">{DOC_TYPE_LABEL[e.doc_type] ?? e.doc_type}</span> <span className="amount font-medium">{new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(Number(e.value))}</span>{e.page ? <span className="text-slate-400"> p.{e.page}</span> : null}
              </Link>
            ))}
          </div>
        )}
      </div>
      <span className="shrink-0 text-xs tabular-nums text-slate-500">{f.points} pts</span>
    </li>
  );
}

export default function Summary() {
  const id = Number(useParams().caseId);
  const cs = useCase(id);
  const docs = useDocuments(id);
  const findings = useFindings(id);
  const risk = useRisk(id);
  const qc = useQueryClient();
  const toast = useToast();
  const run = useMutation({
    mutationFn: () => api<ProcessResult>(`/cases/${id}/process`, { method: "POST" }),
    onSuccess: (r) => { toast.push(`${r.findings} findings, ${r.risk_outcome}`, "ok"); qc.invalidateQueries(); },
    onError: (e: Error) => toast.push(e.message, "error"),
  });
  const report = useMutation({ mutationFn: async () => downloadBlob(await api<Blob>(`/cases/${id}/report.pdf`), `docsentry_case_${id}.pdf`), onError: (e: Error) => toast.push(e.message, "error") });
  if (cs.isLoading || docs.isLoading) return <Skeleton rows={8} />;
  if (cs.error || !cs.data) return <ErrorBox error={cs.error ?? "Case not found"} />;
  const c = cs.data;
  const ds = docs.data ?? [];
  const processed = ds.filter((d) => d.status === "processed").length;
  const failed = ds.filter((d) => d.status === "failed" || d.status === "unsupported");
  const analysed = processed > 0 && !!risk.data?.breakdown && Object.keys(risk.data.breakdown).length > 0;
  const issues = (findings.data ?? []).filter((f) => f.severity !== "info").sort((a, b) => RANK[a.severity] - RANK[b.severity] || b.points - a.points);
  const tone = outcomeTone(c.risk_outcome);
  const steps = [
    { label: "Upload", hint: ds.length ? `${ds.length} files` : undefined, state: ds.length ? "done" : "active" },
    { label: "Extract", hint: processed ? `${processed} read` : undefined, state: run.isPending ? "active" : processed ? "done" : ds.length ? "idle" : "idle" },
    { label: "Compare", hint: analysed ? `${(risk.data?.breakdown?.checks ?? []).filter((x: any) => x.status === "evaluated").length} checks` : undefined, state: run.isPending ? "active" : analysed ? "done" : "idle" },
    { label: "Score", state: run.isPending ? "active" : analysed ? "done" : "idle" },
  ] as const;
  return (
    <div className="animate-fade space-y-6">
      <div className="card flex flex-col gap-6 p-6 md:flex-row md:items-center">
        {analysed ? <ScoreRing score={c.risk_score} tone={tone} /> : <div className="flex h-[132px] w-[132px] shrink-0 items-center justify-center rounded-full border-[10px] border-line text-center text-sm leading-tight text-muted">not yet<br />analysed</div>}
        <div className="min-w-0 flex-1">
          <div className="eyebrow">Case risk score and outcome</div>
          <h1 className="mt-1 text-2xl font-semibold"><Badge tone={analysed ? tone : "info"}>{analysed ? c.risk_outcome : ds.length ? "Not analysed yet" : "No documents"}</Badge></h1>
          <p className="mt-2 max-w-xl text-sm text-slate-600 dark:text-slate-300">
            {!ds.length ? "Upload the documents of this case to begin." : !analysed ? "Documents are uploaded. Run the analysis to extract, compare and score them." :
              c.risk_outcome.startsWith("Insufficient") ? `Not enough evidence for a case assessment: ${risk.data?.breakdown?.insufficient_reason ?? "too few documents or checks"}. The ${c.risk_score} point(s) shown are listed for transparency; they are not an outcome. A single-document scan gives a document security score on the Scan page.` :
              `${issues.length} discrepanc${issues.length === 1 ? "y" : "ies"} found across ${processed} document${processed === 1 ? "" : "s"}; ${Math.round(c.evidence_coverage * 100)}% of applicable checks were evaluated. This is an investigation recommendation, not a fraud judgement.`}
          </p>
          <div className="mt-4"><Stepper steps={steps as any} /></div>
        </div>
        <div className="flex shrink-0 flex-col gap-2">
          {!analysed || failed.length > 0 ? <button className="btn-primary justify-center" disabled={run.isPending || !ds.length} onClick={() => run.mutate()}><Play className="h-4 w-4" />{run.isPending ? "Analysing…" : "Run analysis"}</button> : null}
          {analysed && <button className="btn-primary justify-center" disabled={report.isPending} onClick={() => report.mutate()}><FileDown className="h-4 w-4" />{report.isPending ? "Preparing…" : "Download report"}</button>}
          {!ds.length && <Link to="../upload" className="btn-secondary justify-center">Upload documents</Link>}
          {analysed && <Link to="../graph" className="btn-secondary justify-center">Evidence graph</Link>}
        </div>
      </div>
      {failed.length > 0 && <ErrorBox error={`${failed.length} document(s) could not be read: ${failed.map((d) => `${d.original_filename} (${d.error_message || d.status})`).join("; ")}`} />}
      <Explain points={["Documents were uploaded with generic names; type and content are read from the text, so nothing is keyed on a filename.", "Cross-document rules declare which document types they need and only run when those are present; evidence coverage is checks evaluated over checks applicable.", "Each discrepancy links to the page and field it came from. Click an amount to open the viewer at that spot."]} />
      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <section className="card p-5">
          <div className="flex items-baseline justify-between"><h2 className="font-semibold">What the documents disagree on</h2><Link className="link text-xs" to="../findings">All findings</Link></div>
          {!analysed ? <div className="mt-4"><Empty title="Nothing analysed yet" hint="Run the analysis to see discrepancies with their amounts and source pages." /></div>
            : issues.length === 0 ? <div className="mt-4"><Empty title="No discrepancies above informational level" hint="Agreement between documents does not establish that any document is authentic." /></div>
              : <ul className="stagger mt-2 divide-y divide-slate-100 dark:divide-ink-700">{issues.slice(0, 8).map((f) => <Discrepancy key={f.id} f={f} />)}</ul>}
        </section>
        <section className="card p-5">
          <h2 className="font-semibold">Documents</h2>
          {!ds.length ? <div className="mt-4"><Empty title="No documents" /></div> : (
            <ul className="mt-3 space-y-2">
              {ds.map((d) => (
                <li key={d.id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 px-3 py-2 dark:border-ink-600">
                  <div className="min-w-0"><Link className="block truncate text-sm font-medium hover:underline" to={`../documents/${d.id}`}>{d.original_filename}</Link><div className="text-xs text-slate-500">{DOC_TYPE_LABEL[d.doc_type] ?? d.doc_type}, {d.page_count} page{d.page_count === 1 ? "" : "s"}</div></div>
                  <Badge tone={statusTone(d.status)}>{d.status}</Badge>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}