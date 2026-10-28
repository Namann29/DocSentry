import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useOutletContext, useParams } from "react-router-dom";
import { FileDown } from "lucide-react";
import { api, downloadBlob } from "../../api/client";
import type { Case } from "../../api/types";
import { useAuth } from "../../auth";
import { Badge, Card, PageHeader, useToast } from "../../components/ui";

const SECTIONS = ["Case overview", "Documents with hashes", "Extraction summary and correction rate", "Verification results by taxonomy level", "Financial analysis", "Cross-document discrepancies", "Risk breakdown (every point attributed)", "Evidence references", "Investigation timeline", "Human review outcome", "Verification limitations"];

export default function Reports() {
  const id = Number(useParams().caseId);
  const cs = useOutletContext<Case>();
  const { user } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const [outcome, setOutcome] = useState("escalate");
  const [note, setNote] = useState("");
  const gen = useMutation({
    mutationFn: async () => downloadBlob(await api<Blob>(`/cases/${id}/report.pdf`), `docsentry_case_${id}.pdf`),
    onSuccess: () => toast.push("Report generated and downloaded", "ok"),
    onError: (e: Error) => toast.push(e.message, "error"),
  });
  const review = useMutation({
    mutationFn: () => api(`/cases/${id}/review`, { method: "POST", json: { outcome, note } }),
    onSuccess: () => { toast.push("Review recorded", "ok"); qc.invalidateQueries({ queryKey: ["case", id] }); },
    onError: (e: Error) => toast.push(e.message, "error"),
  });
  const canReview = user?.role === "admin" || user?.role === "reviewer";
  return (
    <div>
      <PageHeader title="Reports" subtitle="A PDF generated from the current state of the case. Generation is logged." actions={<button className="btn-primary" disabled={gen.isPending} onClick={() => gen.mutate()}><FileDown className="h-4 w-4" />{gen.isPending ? "Generating…" : "Generate & download PDF"}</button>} />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Report contents"><ol className="list-decimal space-y-1 pl-5 text-sm">{SECTIONS.map((s) => <li key={s}>{s}</li>)}</ol></Card>
        <Card title="Human review">
          <div className="mb-3 text-sm">Current: {cs.review_outcome ? <Badge tone="ok">{cs.review_outcome}</Badge> : <Badge tone="info">not reviewed</Badge>}{cs.review_note && <span className="ml-2 text-slate-500">{cs.review_note}</span>}</div>
          {canReview ? (
            <div className="space-y-2">
              <select className="input" value={outcome} onChange={(e) => setOutcome(e.target.value)}><option value="cleared">Cleared</option><option value="escalate">Escalate</option><option value="needs_more_evidence">Needs more evidence</option><option value="rejected">Rejected</option></select>
              <textarea className="input" rows={3} placeholder="Reviewer note" value={note} onChange={(e) => setNote(e.target.value)} />
              <button className="btn-primary" disabled={review.isPending} onClick={() => review.mutate()}>Record review</button>
            </div>
          ) : <div className="text-sm text-slate-500">Only reviewers and admins can record a review outcome (role: {user?.role}).</div>}
        </Card>
      </div>
    </div>
  );
}