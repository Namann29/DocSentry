import { useParams } from "react-router-dom";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useDocument, useDocuments, useFindings } from "../../api/hooks";
import { inr } from "../../api/types";
import { Card, PageHeader, Skeleton, Stat } from "../../components/ui";
import { FindingsList } from "./Findings";

export default function Financial() {
  const id = Number(useParams().caseId);
  const docs = useDocuments(id);
  const statement = docs.data?.find((d) => d.doc_type === "bank_statement" && d.status === "processed");
  const detail = useDocument(statement?.id);
  const findings = useFindings(id, "financial");
  const p = detail.data?.parsed ?? {};
  const txns: any[] = p.transactions ?? [];
  const chart = txns.map((t) => ({ date: t.date, balance: Number(t.balance ?? 0) }));
  const credits = txns.filter((t) => t.credit).reduce((a, t) => a + Number(t.credit), 0);
  const debits = txns.filter((t) => t.debit).reduce((a, t) => a + Number(t.debit), 0);
  return (
    <div>
      <PageHeader title="Financial analysis" subtitle="Decimal arithmetic throughout: running-balance reconciliation, salary-slip and invoice arithmetic, income identification, statistical outliers (which are not fraud)." />
      {statement ? (
        <>
          <div className="mb-6 grid gap-4 md:grid-cols-4">
            <Stat label="Transactions" value={txns.length} hint={`${p.period_from ?? "?"} â†’ ${p.period_to ?? "?"}`} />
            <Stat label="Opening â†’ closing" value={<span className="text-base">{inr(p.opening_balance)} â†’ {inr(p.closing_balance)}</span>} />
            <Stat label="Total credits" value={<span className="text-base">{inr(credits)}</span>} />
            <Stat label="Total debits" value={<span className="text-base">{inr(debits)}</span>} />
          </div>
          <Card title="Running balance" className="mb-6">
            {detail.isLoading ? <Skeleton /> : (
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={chart}><XAxis dataKey="date" fontSize={10} /><YAxis fontSize={10} tickFormatter={(v) => `${Math.round(v / 1000)}k`} /><Tooltip formatter={(v: number) => inr(v)} /><Line type="stepAfter" dataKey="balance" stroke="#1e3a5f" dot={false} strokeWidth={2} /></LineChart>
              </ResponsiveContainer>
            )}
          </Card>
        </>
      ) : <Card className="mb-6"><div className="text-sm text-slate-500">No processed bank statement in this case; statement charts are unavailable.</div></Card>}
      {findings.isLoading ? <Skeleton /> : <FindingsList findings={findings.data ?? []} emptyHint="Financial checks run on bank statements, salary slips and invoices." />}
    </div>
  );
}