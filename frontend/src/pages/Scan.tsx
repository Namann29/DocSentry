import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type DragEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { FileDown, RotateCcw } from "lucide-react";
import { api, downloadBlob } from "../api/client";
import type { Contribution, ScanResponse, SecurityScan } from "../api/types";
import { DOC_TYPE_LABEL } from "../api/types";
import { Badge, Empty, useToast } from "../components/ui";
import { ScoreRing } from "../components/Progress";
import DocMotif from "../components/DocMotif";
import { Explain } from "../components/Explain";

type RowStatus = "pass" | "warn" | "fail" | "na";
interface Row { status: RowStatus; name: string; result: string; note?: string }
const DOT: Record<RowStatus, string> = { pass: "bg-emerald-500", warn: "bg-amber-500", fail: "bg-red-500", na: "bg-slate-300" };
const MID = "\u00B7";
const PORTALS: { key: string; label: string; checks: string }[] = [
  { key: "", label: "Any document", checks: "Type is detected from the content." },
  { key: "aadhaar", label: "Aadhaar", checks: "12-digit number with Verhoeff checksum, masked display, name, date of birth, gender." },
  { key: "pan_card", label: "PAN", checks: "PAN structure and holder-type code, surname initial, name, father name, date of birth." },
  { key: "bank_statement", label: "Bank statement", checks: "Account details, transaction table, running-balance reconciliation, salary credits." },
  { key: "salary_slip", label: "Salary slip", checks: "Earnings, deductions, net pay arithmetic, employer, masked PAN and account." },
  { key: "invoice", label: "GST invoice", checks: "GSTIN check digits, line items, tax split, totals." },
  { key: "employment_letter", label: "Employment letter", checks: "Employer, employee, designation, salary figures, joining date." },
];

function sevOf(c?: Contribution): RowStatus { return !c ? "pass" : c.points >= 30 ? "fail" : "warn"; }

function rows(s: SecurityScan): { title: string; rows: Row[] }[] {
  const na = (check: string) => s.not_checked.find((n) => n.check === check);
  const contrib = (check: string) => s.contributions.find((c) => c.check === check);
  const st = s.structure;
  const structure: Row[] = na("structure") ? [{ status: "na", name: "Structural checks", result: "Not checked", note: na("structure")!.reason }] : [
    { status: st.has_text_layer ? "pass" : "warn", name: "Text layer", result: st.has_text_layer ? "Present" : "Absent (scanned image)", note: st.has_text_layer ? "Fields and fonts can be inspected." : "Only structure and metadata can be checked without OCR." },
    { status: st.incremental_updates ? "warn" : "pass", name: "Incremental updates", result: st.incremental_updates ? `${st.incremental_updates} re-save${st.incremental_updates === 1 ? "" : "s"} after creation` : "None", note: st.incremental_updates ? "The file was modified and saved over itself. Form fills and linearised files also do this." : "Single save." },
    ...(["javascript", "embedded_file", "open_action", "additional_actions"] as const).map((k) => ({ status: (st[k] ? sevOf(contrib(k)) : "pass") as RowStatus, name: k.replace("_", " ").replace(/^\w/, (m) => m.toUpperCase()), result: st[k] ? "Present" : "Not present", note: st[k] ? contrib(k)?.explanation : undefined })),
    { status: st.encrypted_at_upload ? "warn" : "pass", name: "Encryption", result: st.encrypted_at_upload ? "Password-protected, decrypted in memory" : "Not encrypted" },
  ];
  const md = s.metadata;
  const metadata: Row[] = na("metadata") ? [{ status: "na", name: "Metadata", result: "Not checked", note: na("metadata")!.reason }] : [
    { status: "pass", name: "Producer / creator", result: `${md.producer ?? "-"} / ${md.creator ?? "-"}` },
    { status: "pass", name: "Created / modified", result: `${md.created ? md.created.replace("T", " ") : "-"} / ${md.modified ? md.modified.replace("T", " ") : "-"}` },
    ...md.issues.map((i) => ({ status: sevOf(s.contributions.find((c) => c.category === "metadata" && c.points > 0)) as RowStatus, name: "Metadata consistency", result: i })),
    ...(md.issues.length ? [] : [{ status: "pass" as RowStatus, name: "Metadata consistency", result: "No inconsistencies observed" }]),
  ];
  const mods: Row[] = na("modification_indicators") ? [{ status: "na", name: "Font consistency", result: "Not checked", note: na("modification_indicators")!.reason }]
    : s.modification_indicators.length ? [] : [{ status: "pass", name: "Font consistency", result: "Numeric values use each page's dominant font family", note: "Absence of indicators does not establish authenticity." }];
  const sens: Row[] = na("sensitive_information") ? [{ status: "na", name: "Identifiers", result: "Not checked", note: na("sensitive_information")!.reason }]
    : s.sensitive.length ? [] : [{ status: "pass", name: "Identifiers", result: "No PAN, Aadhaar, GSTIN, account, phone or email found in plain text" }];
  return [{ title: "Document structure", rows: structure }, { title: "Metadata analysis", rows: metadata }, { title: "Potential modification indicators", rows: mods }, { title: "Sensitive information exposure", rows: sens }];
}

function Ledger({ title, items, children }: { title: string; items: Row[]; children?: React.ReactNode }) {
  return (
    <section className="card">
      <header className="border-b border-line px-4 py-2.5"><h2 className="text-sm font-semibold">{title}</h2></header>
      <ul className="divide-y divide-line/60">
        {items.map((r, i) => (
          <li key={i} className="grid grid-cols-[12px_1fr_1.3fr] items-start gap-3 px-4 py-2.5 text-sm">
            <span className={`mt-1.5 h-2.5 w-2.5 rounded-full ${DOT[r.status]}`} aria-label={r.status} />
            <span className="font-medium">{r.name}</span>
            <span><span className={r.status === "na" ? "text-muted" : ""}>{r.result}</span>{r.note && <span className="block text-xs text-muted">{r.note}</span>}</span>
          </li>
        ))}
      </ul>
      {children}
    </section>
  );
}

const kindLabel = (kind: string) =>
  kind === "pan" || kind === "gstin" || kind === "ifsc" ? kind.toUpperCase() : kind === "aadhaar_invalid" ? "Aadhaar-format number, checksum failed" : kind[0].toUpperCase() + kind.slice(1);

export default function Scan() {
  const toast = useToast();
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [password, setPassword] = useState("");
  const params = useParams();
  const [portal, setPortal] = useState(PORTALS.some((p) => p.key === params.portal) ? (params.portal as string) : "");
  const [drag, setDrag] = useState(false);
  const [result, setResult] = useState<ScanResponse | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const scan = useMutation({
    mutationFn: async () => { const fd = new FormData(); fd.append("file", file!); if (password) fd.append("password", password); if (portal) fd.append("expected_type", portal); return api<ScanResponse>("/scan", { method: "POST", body: fd }); },
    onSuccess: (r) => { setResult(r); qc.invalidateQueries({ queryKey: ["cases"] }); },
    onError: (e: Error) => toast.push(e.message, "error"),
  });
  const report = useMutation({ mutationFn: async () => downloadBlob(await api<Blob>(`/cases/${result!.case_id}/report.pdf`), `docsentry_case_${result!.case_id}.pdf`), onError: (e: Error) => toast.push(e.message, "error") });
  const onDrop = (e: DragEvent) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) { setFile(f); setResult(null); } };
  const s = result?.scan ?? null;
  const tone = !s ? "info" : s.level.startsWith("Low") ? "ok" : s.level.startsWith("Review") ? "medium" : "high";
  const groups = s ? rows(s) : [];
  const byKind = s ? s.sensitive.reduce<Record<string, typeof s.sensitive>>((acc, x) => { (acc[x.kind] ??= []).push(x); return acc; }, {}) : {};
  const q = result?.ocr_quality?.[0];
  const mc = q ? Number(q.ocr_mean_confidence ?? 0) : 0;
  const fields = Object.fromEntries(Object.entries(result?.fields ?? {}).filter(([, v]) => v !== null && v !== "" && typeof v !== "boolean" && !(typeof v === "string" && /^0+(\.0+)?$/.test(v))));
  return (
    <div className="space-y-8">
      {!result && (
        <section className="workspace relative overflow-hidden px-8 py-8 md:px-10">
          <div className="grid items-center gap-10 lg:grid-cols-[1fr_280px]">
            <div>
              <div className="eyebrow text-accent">Document security scan</div>
              <h1 className="mt-3 max-w-2xl font-display text-[2.1rem] font-800 leading-[1.08] tracking-tight text-fg md:text-[2.5rem]">Drop a document. See what changed, what's exposed, and what it proves.</h1>
              <p className="mt-3 max-w-xl text-[15px] leading-relaxed text-fg2">Structure, metadata, font consistency and sensitive identifiers, each reported with what it means. Photos and scans go through OCR with a quality gate. Results are indicators under a published scoring policy, never a determination of fraud.</p>
              <div className="mt-6 flex flex-wrap gap-2" role="tablist" aria-label="Document type">
                {PORTALS.map((p) => <button key={p.key} role="tab" aria-selected={portal === p.key} className={`chip ${portal === p.key ? "border-accent text-accent" : ""}`} onClick={() => setPortal(p.key)}>{p.label}</button>)}
              </div>
              <p className="mt-2 text-xs text-fg2">{PORTALS.find((p) => p.key === portal)?.checks}</p>
              <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={onDrop}
                className={`mt-6 rounded-xl border border-dashed px-6 py-6 transition-colors duration-150 ${drag ? "border-accent bg-accent/10" : "border-line bg-surface"}`}>
                <label htmlFor="scan-file" className="sr-only">Choose a document</label>
                <input id="scan-file" ref={inputRef} type="file" accept=".pdf,.png,.jpg,.jpeg" className="sr-only" onChange={(e) => { const f = e.target.files?.[0]; if (f) { setFile(f); setResult(null); } e.target.value = ""; }} />
                {file ? (
                  <div className="flex flex-wrap items-center justify-between gap-4">
                    <div><div className="font-medium text-fg">{file.name}</div><div className="font-mono text-[11px] text-fg2">{(file.size / 1024).toFixed(0)} KB {MID} {file.type || "unknown type"}</div></div>
                    <button className="btn-secondary" disabled={scan.isPending} onClick={() => inputRef.current?.click()}>Choose a different file</button>
                  </div>
                ) : (
                  <div className="flex flex-wrap items-center justify-between gap-4">
                    <div><div className="font-medium text-fg">Drag a file here</div><div className="text-xs text-fg2">PDF, PNG or JPEG up to 25 MB. The type is verified from the file's bytes, not its name.</div></div>
                    <button className="btn-secondary" onClick={() => inputRef.current?.click()}>Browse files</button>
                  </div>
                )}
              </div>
              <div className="mt-4 flex flex-wrap items-end gap-4">
                <div className="w-full sm:w-64"><label className="label" htmlFor="scan-pw">PDF password, if protected</label><input id="scan-pw" className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="off" disabled={scan.isPending} /></div>
                <button className="btn-primary h-10 px-5 text-[15px]" disabled={!file || scan.isPending} onClick={() => scan.mutate()}>{scan.isPending ? "Inspecting document" + "\u2026" : "Scan document"}</button>
                {scan.isPending && <p role="status" className="text-xs text-fg2">One request: upload, OCR if needed, structure, metadata, fonts and identifiers are processed together.</p>}
              </div>
            </div>
            <DocMotif scanning={scan.isPending} className="mx-auto h-[300px] w-[230px] text-fg2" />
          </div>
        </section>
      )}
      {result && (
        <section className="stagger space-y-6">
          <Explain points={["Structure and metadata come from the PDF itself: end-of-file markers count re-saves; dates and producer come from the document info dictionary.", "Modification indicators compare each number's font family with the page's dominant font. Editors leave their font behind. Amber means potential, not proof.", "Images and scans are read by OCR (EasyOCR with Tesseract as a second opinion); every word carries a confidence and the page reports its quality.", "Sensitive identifiers are matched by pattern and checksum, shown masked; the unmasked value is never stored."]} />
          <div className="card flex flex-col gap-6 p-6 md:flex-row md:items-center">
            {s ? <ScoreRing score={s.score} tone={tone} /> : <div className="h-[132px] w-[132px]" />}
            <div className="min-w-0 flex-1">
              <div className="eyebrow">Document security score</div>
              <h1 className="mt-1 text-2xl font-semibold">{s ? <Badge tone={tone}>{s.level}</Badge> : <Badge tone="warn">Scan incomplete</Badge>}</h1>
              <p className="mt-1 text-sm text-fg2">{result.filename}, read as {DOC_TYPE_LABEL[result.doc_type] ?? result.doc_type}{result.weak_parse ? " (low confidence: its key field was not found)" : result.classification_confidence !== undefined && result.doc_type !== "unknown" ? ` (confidence ${result.classification_confidence.toFixed(2)})` : ""} via {result.extraction_method ?? "unknown method"}, {result.page_count} page{result.page_count === 1 ? "" : "s"}.{result.error_message ? ` ${result.error_message}` : ""}</p>
              {result.type_mismatch && <p className="mt-2 text-sm text-amber-500">You selected {PORTALS.find((p) => p.key === result.expected_type)?.label ?? result.expected_type}; the content reads as {DOC_TYPE_LABEL[result.doc_type] ?? result.doc_type}. Treat this as an indicator and check the file.</p>}
              {result.type_assumed && <p className="mt-2 text-sm text-fg2">The content alone was not enough to classify this file; the type was taken from your selection and fields were extracted on that basis.</p>}
              {s && <p className="mt-2 max-w-xl text-xs text-muted">{s.note} This per-document score covers structure, metadata, fonts and identifiers; the case risk score on the investigation summary is a separate policy that also counts arithmetic and cross-document findings. Policy {s.version}; review from {s.thresholds.review}, high from {s.thresholds.high} points.</p>}
            </div>
            <div className="flex shrink-0 flex-col gap-2">
              <Link className="btn-primary justify-center" to={`/cases/${result.case_id}/documents/${result.document_id}?mods=1`}>View document</Link>
              <button className="btn-secondary justify-center" onClick={() => report.mutate()} disabled={report.isPending}><FileDown className="h-4 w-4" />{report.isPending ? "Preparing" + "\u2026" : "Download report"}</button>
              <Link className="btn-secondary justify-center" to={`/cases/${result.case_id}/summary`}>Open full investigation</Link>
              <button className="btn-secondary justify-center" onClick={() => { setResult(null); setFile(null); setPassword(""); }}><RotateCcw className="h-4 w-4" />Start another scan</button>
            </div>
          </div>
          {Object.keys(fields).length > 0 && (
            <Ledger title="Extracted fields" items={Object.entries(fields).slice(0, 14).map(([k, v]) => ({ status: "pass" as RowStatus, name: k.replace(/_/g, " "), result: String(v) }))} />
          )}
          {Object.keys(fields).length === 0 && (
            <Ledger title="Extracted fields" items={[{ status: "na", name: "Fields", result: result.doc_type === "unknown" ? "No document type matched" : "None extracted", note: result.doc_type === "unknown" ? "The content did not resemble any supported document type closely enough; only structure, metadata and identifier checks were run." : "The parser for this type found no values; the classification is uncertain." }]} />
          )}
          {q && (
            <Ledger title="Text recognition (OCR)" items={[
              { status: "pass", name: "Engine", result: String(q.engine ?? result.extraction_method ?? ""), note: q.regions_by_engine ? "Regions won: " + Object.entries(q.regions_by_engine).map(([k, v]) => `${k} ${v}`).join(", ") : undefined },
              { status: mc >= 0.6 ? "pass" : "warn", name: "Mean word confidence", result: mc.toFixed(2), note: mc < 0.6 ? "Low: text read from this image is unreliable. Findings that depend on it are weighted down; verify fields against the original." : "Text was read with reasonable confidence." },
              { status: "pass", name: "Image", result: `${q.width}${"\u00D7"}${q.height} px after upscaling, blur ${q.blur_variance}, contrast ${q.contrast}`, note: q.deskew_degrees ? `Deskewed by ${q.deskew_degrees}${"\u00B0"}` : undefined },
              ...((q.warnings ?? []) as string[]).map((w) => ({ status: "warn" as RowStatus, name: "Image quality", result: w })),
            ]} />
          )}
          {s && (
            <div className="grid gap-6 lg:grid-cols-2">
              {groups.map((g) => (
                <Ledger key={g.title} title={g.title} items={g.rows}>
                  {g.title.startsWith("Potential") && s.modification_indicators.length > 0 && (
                    <table className="border-t border-line">
                      <thead><tr><th className="th">Page</th><th className="th">Text</th><th className="th">Font observed</th><th className="th">Why flagged</th></tr></thead>
                      <tbody>{s.modification_indicators.map((m, i) => (
                        <tr key={i}><td className="td num">{m.page}</td><td className="td amount"><Link className="link" to={`/cases/${result.case_id}/documents/${result.document_id}?page=${m.page}&mods=1&hl=${i}`}>{m.text}</Link></td><td className="td text-xs">{m.font} {m.size}pt</td><td className="td text-xs text-amber-500">differs from page font family "{m.dominant_font}"; potential modification, not proof</td></tr>
                      ))}</tbody>
                    </table>
                  )}
                  {g.title.startsWith("Sensitive") && s.sensitive.length > 0 && (
                    <ul className="divide-y divide-line/60 border-t border-line">
                      {Object.entries(byKind).map(([kind, items]) => (
                        <li key={kind} className="grid grid-cols-[12px_1fr_1.3fr] gap-3 px-4 py-2.5 text-sm"><span className="mt-1.5 h-2.5 w-2.5 rounded-full bg-amber-500" /><span className="font-medium">{kindLabel(kind)}</span>
                          <span>{items.map((x, i) => <span key={i} className="amount mr-2 inline-block">{x.masked} <span className="text-xs text-muted">p.{x.page}</span></span>)}<span className="block text-xs text-muted">Masked; the unmasked value was not stored.</span></span></li>
                      ))}
                    </ul>
                  )}
                </Ledger>
              ))}
            </div>
          )}
          {!s && <Empty title="No scan result" hint={result.error_message || "The document could not be read."} />}
        </section>
      )}
    </div>
  );
}