import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { Download, Trash2 } from "lucide-react";
import { api, downloadBlob } from "../../api/client";
import { useDocuments } from "../../api/hooks";
import { Badge, Card, Empty, PageHeader, Skeleton, useToast } from "../../components/ui";

export default function Vault() {
  const id = Number(useParams().caseId);
  const docs = useDocuments(id);
  const qc = useQueryClient();
  const toast = useToast();
  const download = useMutation({
    mutationFn: async (d: { id: number; original_filename: string }) => downloadBlob(await api<Blob>(`/documents/${d.id}/download`), d.original_filename),
    onError: (e: Error) => toast.push(e.message, "error"),
  });
  const remove = useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) => api(`/documents/${id}?reason=${encodeURIComponent(reason)}`, { method: "DELETE" }),
    onSuccess: () => { toast.push("Document soft-deleted; retained for audit", "ok"); qc.invalidateQueries({ queryKey: ["documents", id] }); },
    onError: (e: Error) => toast.push(e.message, "error"),
  });
  return (
    <div>
      <PageHeader title="Evidence vault" subtitle="Private storage with SHA-256 fingerprints computed at upload. Downloads and views are written to the audit log. Deletion is soft and requires a reason." />
      <Card>
        {docs.isLoading ? <Skeleton /> : !docs.data?.length ? <Empty title="Vault is empty" /> : (
          <table className="w-full"><thead><tr><th className="th">File</th><th className="th">SHA-256</th><th className="th">Size</th><th className="th">Uploaded</th><th className="th">Flags</th><th className="th"></th></tr></thead>
            <tbody>{docs.data.map((d) => (
              <tr key={d.id}>
                <td className="td font-medium">{d.original_filename}</td><td className="td mono break-all">{d.sha256}</td><td className="td">{(d.size_bytes / 1024).toFixed(0)} KB</td>
                <td className="td text-xs text-slate-500">{new Date(d.created_at).toLocaleString()}</td>
                <td className="td">{d.security_flags.length ? d.security_flags.map((f) => <Badge key={f} tone="warn">{f}</Badge>) : <Badge tone="ok">clean</Badge>}</td>
                <td className="td"><div className="flex gap-1">
                  <button className="btn-secondary" onClick={() => download.mutate(d)}><Download className="h-4 w-4" /></button>
                  <button className="btn-danger" onClick={() => { const reason = window.prompt("Reason for deletion (recorded in the audit log):"); if (reason && reason.length >= 3) remove.mutate({ id: d.id, reason }); }}><Trash2 className="h-4 w-4" /></button>
                </div></td>
              </tr>))}</tbody></table>
        )}
      </Card>
    </div>
  );
}