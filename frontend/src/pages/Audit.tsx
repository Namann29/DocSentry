import { useMutation } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAudit, useDocuments } from "../api/hooks";
import { useAuth } from "../auth";
import { Badge, Card, Empty, ErrorBox, PageHeader, Skeleton, useToast } from "../components/ui";
import { Explain } from "../components/Explain";

export default function Audit() {
  const { caseId } = useParams();
  const id = caseId ? Number(caseId) : NaN;
  const { user } = useAuth();
  const canRead = user?.role === "admin" || user?.role === "reviewer";
  const audit = useAudit();
  const docs = useDocuments(id);
  const toast = useToast();
  const verify = useMutation({ mutationFn: () => api<any>("/audit/verify"), onSuccess: (r) => toast.push(r.ok ? `Chain intact: ${r.checked} events, head ${r.head_hash.slice(0, 12)}…` : `Chain BROKEN at event ${r.first_bad_id}`, r.ok ? "ok" : "error"), onError: (e: Error) => toast.push(e.message, "error") });
  const docIds = new Set((docs.data ?? []).map((d) => String(d.id)));
  const events = (audit.data ?? []).filter((e) => !caseId || (e.resource_type === "case" && e.resource_id === String(id)) || (e.resource_type === "document" && docIds.has(e.resource_id)));
  return (
    <div>
      <PageHeader title={caseId ? "Case audit history" : "Audit history"} subtitle="Append-only, hash-linked log (tamper-evident, not a blockchain). Views, downloads, uploads, corrections and processing runs are recorded; no raw PII." actions={canRead && <button className="btn-secondary" onClick={() => verify.mutate()} disabled={verify.isPending}>Verify chain</button>} />
      <div className="mb-4"><Explain points={["Every row stores the hash of the previous row; Verify chain recomputes all of them. A changed or deleted row breaks the chain.", "A database trigger blocks UPDATE and DELETE on this table. Tamper-evident, not a blockchain: a database superuser could rewrite it.", "Details contain no raw personal data; only identifiers, hashes and counts."]} /></div>
      {!canRead ? <Empty title="Audit log is restricted" hint={`Your role (${user?.role}) cannot read the audit log; admins and reviewers can.`} /> : audit.error ? <ErrorBox error={audit.error} /> : (
        <Card>
          {audit.isLoading ? <Skeleton rows={8} /> : events.length === 0 ? <Empty title="No events" /> : (
            <table className="w-full"><thead><tr><th className="th">Time</th><th className="th">Action</th><th className="th">Resource</th><th className="th">Actor</th><th className="th">Detail</th><th className="th">Hash</th></tr></thead>
              <tbody>{events.map((e) => <tr key={e.id}><td className="td text-xs text-slate-500">{e.created_at.slice(0, 19).replace("T", " ")}</td><td className="td"><Badge tone="info">{e.action}</Badge></td><td className="td text-xs">{e.resource_type} {e.resource_id}</td><td className="td text-xs">{e.actor_id ?? "-"}</td><td className="td mono text-slate-500">{JSON.stringify(e.detail).slice(0, 90)}</td><td className="td mono text-slate-400">{e.hash.slice(0, 10)}…</td></tr>)}</tbody></table>
          )}
        </Card>
      )}
    </div>
  );
}