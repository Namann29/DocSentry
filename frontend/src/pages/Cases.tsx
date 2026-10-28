import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useCases } from "../api/hooks";
import { Badge, Empty, ErrorBox, PageHeader, Skeleton, outcomeTone } from "../components/ui";

export default function Cases() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const cases = useCases(q, status);
  const nav = useNavigate();
  return (
    <div>
      <PageHeader title="Cases" subtitle="A case groups the documents of one investigation." actions={<Link to="/cases/new" className="btn-primary">New case</Link>} />
      <div className="mb-4 flex gap-2">
        <input className="input max-w-sm" placeholder="Search by title" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search cases" />
        <select className="input max-w-[170px]" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filter by status">
          <option value="">Any status</option><option value="open">Open</option><option value="reviewed">Reviewed</option><option value="closed">Closed</option>
        </select>
      </div>
      {cases.error && <ErrorBox error={cases.error} />}
      {cases.isLoading ? <Skeleton rows={6} /> : (cases.data ?? []).length === 0 ? (
        <Empty title="No cases match" hint="Change the search or create a new case." action={<Link to="/cases/new" className="btn-secondary">New case</Link>} />
      ) : (
        <table>
          <thead><tr><th className="th">Title</th><th className="th">Type</th><th className="th">Status</th><th className="th">Outcome</th><th className="th num">Score</th><th className="th num">Coverage</th><th className="th num">Docs</th><th className="th num">Findings</th><th className="th">Updated</th></tr></thead>
          <tbody>
            {cases.data!.map((c) => (
              <tr key={c.id} onClick={() => nav(`/cases/${c.id}`)} className="cursor-pointer hover:bg-white dark:hover:bg-ink-800">
                <td className="td font-medium">{c.title}</td><td className="td">{c.case_type.replace("_", " ")}</td>
                <td className="td">{c.status}{c.review_outcome && <span className="text-slate-500">, {c.review_outcome.replace("_", " ")}</span>}</td>
                <td className="td"><Badge tone={outcomeTone(c.risk_outcome)}>{c.risk_outcome}</Badge></td>
                <td className="td num">{c.risk_score}</td><td className="td num">{Math.round(c.evidence_coverage * 100)}%</td><td className="td num">{c.document_count}</td><td className="td num">{c.finding_count}</td>
                <td className="td text-slate-500">{new Date(c.updated_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}