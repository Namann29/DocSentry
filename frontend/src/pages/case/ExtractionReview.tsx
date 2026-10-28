import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { useDocument, useFields } from "../../api/hooks";
import type { Field } from "../../api/types";
import { Badge, Card, Empty, ErrorBox, PageHeader, Skeleton, useToast } from "../../components/ui";

export default function ExtractionReview() {
  const { caseId, docId } = useParams();
  const did = Number(docId);
  const qc = useQueryClient();
  const toast = useToast();
  const doc = useDocument(did);
  const fields = useFields(did);
  const [filter, setFilter] = useState("");
  const [editing, setEditing] = useState<Field | null>(null);
  const [value, setValue] = useState("");
  const save = useMutation({
    mutationFn: () => api<Field>(`/documents/${did}/fields/${editing!.id}`, { method: "PATCH", json: { value } }),
    onSuccess: () => { toast.push("Correction saved with provenance. Re-run processing to update findings.", "ok"); setEditing(null); qc.invalidateQueries({ queryKey: ["fields", did] }); qc.invalidateQueries({ queryKey: ["document", did] }); qc.invalidateQueries({ queryKey: ["stats"] }); },
    onError: (e: Error) => toast.push(e.message, "error"),
  });
  const reprocess = useMutation({
    mutationFn: () => api(`/cases/${caseId}/process?force=true`, { method: "POST" }),
    onSuccess: () => { toast.push("Case re-processed with corrections applied", "ok"); qc.invalidateQueries(); },
    onError: (e: Error) => toast.push(e.message, "error"),
  });
  const list = (fields.data ?? []).filter((f) => !filter || f.name.toLowerCase().includes(filter.toLowerCase()) || f.value.toLowerCase().includes(filter.toLowerCase()));
  return (
    <div>
      <PageHeader title="Extraction Review" subtitle={doc.data ? `${doc.data.original_filename} · corrections are stored with the original value and count towards the measured correction rate` : ""}
        actions={<><button className="btn-primary" disabled={reprocess.isPending} onClick={() => reprocess.mutate()}>{reprocess.isPending ? "Re-processing…" : "Re-run analysis"}</button><Link to={`../documents/${did}`} className="btn-secondary">Open viewer</Link></>} />
      {doc.data?.parsed?._warnings?.length ? <div className="mb-4"><ErrorBox error={`Parser warnings: ${doc.data.parsed._warnings.join("; ")}`} /></div> : null}
      <Card actions={<input className="input max-w-xs" placeholder="Filter fields…" value={filter} onChange={(e) => setFilter(e.target.value)} />}>
        {fields.isLoading ? <Skeleton rows={8} /> : list.length === 0 ? <Empty title="No fields" hint="Run processing first, or the parser found nothing for this document type." /> : (
          <table className="w-full">
            <thead><tr><th className="th">Field</th><th className="th">Value</th><th className="th">Normalised</th><th className="th">Confidence</th><th className="th">Page</th><th className="th">Provenance</th><th className="th"></th></tr></thead>
            <tbody>
              {list.map((f) => (
                <tr key={f.id}>
                  <td className="td mono">{f.name}</td>
                  <td className="td">{editing?.id === f.id ? <input className="input" value={value} onChange={(e) => setValue(e.target.value)} autoFocus /> : f.value}</td>
                  <td className="td mono text-slate-500">{f.normalized_value}</td>
                  <td className="td"><div className="h-2 w-24 rounded bg-slate-200 dark:bg-slate-700"><div className={`h-2 rounded ${f.confidence >= 0.9 ? "bg-emerald-500" : f.confidence >= 0.7 ? "bg-amber-500" : "bg-red-500"}`} style={{ width: `${f.confidence * 100}%` }} /></div><span className="text-xs text-slate-500">{f.confidence.toFixed(2)}</span></td>
                  <td className="td"><Link className="underline" to={`../documents/${did}?page=${f.page}&field=${encodeURIComponent(f.name)}`}>{f.page}</Link></td>
                  <td className="td">{f.corrected ? <Badge tone="ok" title={`original: ${f.original_value}`}>manual (was {f.original_value})</Badge> : <Badge tone="info">{f.method}</Badge>}</td>
                  <td className="td">{editing?.id === f.id ? <div className="flex gap-1"><button className="btn-primary" onClick={() => save.mutate()} disabled={save.isPending}>Save</button><button className="btn-secondary" onClick={() => setEditing(null)}>Cancel</button></div> : <button className="btn-secondary" onClick={() => { setEditing(f); setValue(f.value); }}>Correct</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}