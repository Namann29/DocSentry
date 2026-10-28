import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type DragEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { FileUp, Play } from "lucide-react";
import { api } from "../../api/client";
import { useDocuments, useJobs } from "../../api/hooks";
import type { Doc, ProcessResult } from "../../api/types";
import { DOC_TYPE_LABEL } from "../../api/types";
import { Badge, Card, Empty, ErrorBox, PageHeader, Skeleton, statusTone, useToast } from "../../components/ui";

export default function Upload() {
  const id = Number(useParams().caseId);
  const qc = useQueryClient();
  const toast = useToast();
  const docs = useDocuments(id);
  const jobs = useJobs(id);
  const [files, setFiles] = useState<File[]>([]);
  const [password, setPassword] = useState("");
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const upload = useMutation({
    mutationFn: async () => {
      const fd = new FormData();
      files.forEach((f) => fd.append("files", f));
      if (password) fd.append("password", password);
      return api<Doc[]>(`/cases/${id}/documents`, { method: "POST", body: fd });
    },
    onSuccess: (d) => { toast.push(`${d.length} document(s) uploaded`, "ok"); setFiles([]); setPassword(""); qc.invalidateQueries({ queryKey: ["documents", id] }); qc.invalidateQueries({ queryKey: ["case", id] }); },
    onError: (e: Error) => toast.push(e.message, "error"),
  });
  const process = useMutation({
    mutationFn: (force: boolean) => api<ProcessResult>(`/cases/${id}/process?force=${force}`, { method: "POST" }),
    onSuccess: (r) => { toast.push(`Processed ${r.processed}/${r.documents} documents, ${r.findings} findings, ${r.risk_outcome}`, "ok"); qc.invalidateQueries(); },
    onError: (e: Error) => toast.push(e.message, "error"),
  });
  const onDrop = (e: DragEvent) => { e.preventDefault(); setDrag(false); setFiles((f) => [...f, ...Array.from(e.dataTransfer.files)]); };
  return (
    <div>
      <PageHeader title="Upload" subtitle="PDF, PNG or JPEG. Password-protected PDFs are decrypted in memory; the password is never stored." />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Add documents" className="lg:col-span-1">
          <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={onDrop} onClick={() => inputRef.current?.click()}
            className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 text-center ${drag ? "border-navy-500 bg-navy-50 dark:bg-navy-900" : "border-slate-300 dark:border-slate-700"}`}>
            <FileUp className="mb-2 h-6 w-6 text-slate-400" />
            <div className="text-sm font-medium">Drop files here or click to browse</div>
            <div className="text-xs text-slate-500">Max 25 MB each, magic bytes are checked</div>
            <input ref={inputRef} type="file" multiple accept=".pdf,.png,.jpg,.jpeg" className="hidden" onChange={(e) => setFiles((f) => [...f, ...Array.from(e.target.files ?? [])])} />
          </div>
          {files.length > 0 && (
            <ul className="mt-3 space-y-1 text-sm">
              {files.map((f, i) => <li key={i} className="flex justify-between"><span className="truncate">{f.name}</span><button className="text-xs text-red-600" onClick={() => setFiles(files.filter((_, j) => j !== i))}>remove</button></li>)}
            </ul>
          )}
          <label className="label mt-4">PDF password (optional)</label>
          <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Only if a statement is protected" autoComplete="off" />
          <button className="btn-primary mt-3 w-full justify-center" disabled={!files.length || upload.isPending} onClick={() => upload.mutate()}>{upload.isPending ? "Uploading…" : `Upload ${files.length || ""}`}</button>
          {upload.error && <div className="mt-2"><ErrorBox error={upload.error} /></div>}
        </Card>
        <Card title="Documents in case" className="lg:col-span-2" actions={
          <div className="flex gap-2">
            <button className="btn-secondary" disabled={process.isPending || !docs.data?.length} onClick={() => process.mutate(true)}>Re-run all</button>
            <button className="btn-primary" disabled={process.isPending || !docs.data?.length} onClick={() => process.mutate(false)}><Play className="h-4 w-4" />{process.isPending ? "Processing…" : "Run processing"}</button>
          </div>}>
          {docs.isLoading ? <Skeleton /> : !docs.data?.length ? <Empty title="No documents yet" hint="Upload the documents belonging to this case, then run processing." /> : (
            <table className="w-full">
              <thead><tr><th className="th">File</th><th className="th">Type</th><th className="th">Pages</th><th className="th">Status</th><th className="th">Flags</th></tr></thead>
              <tbody>
                {docs.data.map((d) => (
                  <tr key={d.id}>
                    <td className="td"><Link to={`../documents/${d.id}`} className="font-medium hover:underline">{d.original_filename}</Link><div className="text-xs text-slate-500">{(d.size_bytes / 1024).toFixed(0)} KB, {d.sha256.slice(0, 12)}…</div></td>
                    <td className="td">{DOC_TYPE_LABEL[d.doc_type] ?? d.doc_type}{d.status === "processed" && <div className="text-xs text-slate-500">conf {d.classification_confidence.toFixed(2)}</div>}</td>
                    <td className="td">{d.page_count}</td>
                    <td className="td"><Badge tone={statusTone(d.status)}>{d.status}</Badge>{d.error_message && <div className="mt-1 max-w-xs text-xs text-red-600">{d.error_message}</div>}</td>
                    <td className="td">{d.security_flags.map((f) => <Badge key={f} tone="warn">{f}</Badge>)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {process.data && (
            <div className="mt-4 rounded-md bg-slate-50 p-3 text-sm dark:bg-slate-800">
              Last run: {process.data.processed}/{process.data.documents} processed, {process.data.findings} findings, outcome <strong>{process.data.risk_outcome}</strong> (score {process.data.risk_score}, coverage {Math.round(process.data.evidence_coverage * 100)}%).
              {process.data.failed.length > 0 && <div className="text-red-600">Failed: {process.data.failed.join(", ")}</div>}
              <Link to="../risk" className="ml-2 underline">Open risk assessment</Link>
            </div>
          )}
        </Card>
      </div>
      <Card title="Processing jobs" className="mt-6">
        {!jobs.data?.length ? <div className="text-sm text-slate-500">No jobs yet.</div> : (
          <table className="w-full"><thead><tr><th className="th">Job</th><th className="th">Status</th><th className="th">Progress</th><th className="th">Message</th><th className="th">Finished</th></tr></thead>
            <tbody>{jobs.data.map((j) => <tr key={j.id}><td className="td">#{j.id} {j.kind}</td><td className="td"><Badge tone={j.status === "completed" ? "ok" : j.status === "failed" ? "high" : "info"}>{j.status}</Badge></td><td className="td">{j.progress}%</td><td className="td text-xs">{j.message}</td><td className="td text-xs text-slate-500">{j.finished_at ? new Date(j.finished_at).toLocaleString() : "-"}</td></tr>)}</tbody></table>
        )}
      </Card>
    </div>
  );
}