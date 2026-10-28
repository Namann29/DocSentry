import { Link, useNavigate } from "react-router-dom";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { FileSearch } from "lucide-react";
import { useAuditEvents, useCases } from "../api/hooks";
import { useAuth } from "../auth";
import DocMotif from "../components/DocMotif";
import { FeatureHighlights } from "../components/Explain";
import { Badge, Card, Empty, ErrorBox, Skeleton, outcomeTone } from "../components/ui";

const COLORS: Record<string, string> = { "Low observed risk": "var(--sev-ok-hex)", "Review recommended": "var(--sev-warn-hex)", "High observed risk": "var(--sev-high-hex)", "Insufficient evidence": "var(--muted-hex)", "Processing failed": "var(--sev-high-hex)" };

function Figure({ label, value }: { label: string; value: React.ReactNode }) {
  return <div className="border-l border-line pl-4"><div className="font-display text-3xl font-700 tabular-nums leading-none text-fg">{value}</div><div className="mt-1.5 text-xs text-fg2">{label}</div></div>;
}

export default function Overview() {
  const { user } = useAuth();
  const cases = useCases();
  const nav = useNavigate();
  const canAudit = user?.role === "admin" || user?.role === "reviewer";
  const events = useAuditEvents(canAudit);
  const list = cases.data ?? [];
  const byOutcome = Object.keys(COLORS).map((name) => ({ name, value: list.filter((c) => c.risk_outcome === name).length })).filter((d) => d.value > 0);
  const awaiting = list.filter((c) => (c.risk_outcome.startsWith("High") || c.risk_outcome.startsWith("Review")) && !c.review_outcome).length;
  const v = (n: number) => (cases.isLoading ? "…" : n);
  return (
    <div className="space-y-8">
      <section className="workspace relative overflow-hidden px-8 py-8 md:px-10">
        <div className="grid items-center gap-8 lg:grid-cols-[1.25fr_0.75fr]">
          <div className="stagger">
            <div className="eyebrow text-accent">Digital evidence desk</div>
            <h1 className="mt-3 max-w-xl font-display text-[2.4rem] font-800 leading-[1.05] tracking-tight text-fg md:text-[2.9rem]">Every document leaves a trace.</h1>
            <p className="mt-4 max-w-lg text-[15px] leading-relaxed text-fg2">Examine structure, trace inconsistencies, and surface information that deserves a closer look.</p>
            <div className="mt-6 flex flex-wrap gap-2">
              <Link to="/scan" className="btn-primary"><FileSearch className="h-4 w-4" />Scan a document</Link>
              <Link to="/compare" className="btn border border-line text-fg hover:border-accent">Compare versions</Link>
              <Link to="/investigate" className="btn border border-line text-fg hover:border-accent">Salary slip vs statement</Link>
            </div>
            <div className="mt-8 grid grid-cols-2 gap-6 sm:grid-cols-4">
              <Figure label="investigations" value={v(list.length)} />
              <Figure label="documents analysed" value={v(list.reduce((a, c) => a + c.document_count, 0))} />
              <Figure label="awaiting review" value={v(awaiting)} />
              <Figure label="high observed risk" value={v(list.filter((c) => c.risk_outcome.startsWith("High")).length)} />
            </div>
          </div>
          <DocMotif className="mx-auto hidden h-[260px] w-[200px] text-fg2 lg:block" />
        </div>
      </section>
      <FeatureHighlights />
      {cases.error && <ErrorBox error={cases.error} />}
      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <Card title="Recent investigations" actions={<Link className="link text-xs" to="/cases">All investigations</Link>}>
          {cases.isLoading ? <Skeleton rows={6} /> : list.length === 0 ? (
            <Empty title="No investigations yet" hint="Scan a document or generate a sample case to see the pipeline run end to end." action={<Link to="/scan" className="btn-primary">Scan a document</Link>} />
          ) : (
            <table>
              <thead><tr><th className="th">Investigation</th><th className="th num">Docs</th><th className="th num">Score</th><th className="th">Outcome</th><th className="th">Updated</th></tr></thead>
              <tbody className="stagger">
                {[...list].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 10).map((c) => (
                  <tr key={c.id} onClick={() => nav(`/cases/${c.id}`)} className="cursor-pointer transition-colors hover:bg-accent-50/60 dark:hover:bg-white/[0.04]">
                    <td className="td"><div className="font-medium">{c.title}</div><div className="text-xs text-slate-500">{c.case_type.replace("_", " ")}</div></td>
                    <td className="td num">{c.document_count}</td><td className="td num font-mono">{c.risk_score}</td>
                    <td className="td"><Badge tone={outcomeTone(c.risk_outcome)}>{c.risk_outcome}</Badge></td>
                    <td className="td font-mono text-[11px] text-slate-500">{new Date(c.updated_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
        <Card title="Risk distribution">
          {byOutcome.length === 0 ? <Empty title="No outcomes yet" hint="Outcomes appear once an investigation has been analysed." /> : (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={byOutcome} dataKey="value" nameKey="name" innerRadius={58} outerRadius={90} paddingAngle={2} stroke="none" isAnimationActive animationDuration={700}>
                  {byOutcome.map((d) => <Cell key={d.name} fill={COLORS[d.name]} />)}
                </Pie>
                <Tooltip /><Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>
      {canAudit && (
        <Card title="Recent activity">
          {events.isLoading ? <Skeleton /> : !events.data?.length ? <Empty title="No activity yet" /> : (
            <ul className="stagger divide-y divide-ink-900/[0.06] text-sm dark:divide-white/[0.06]">
              {events.data.slice(0, 8).map((e) => <li key={e.id} className="flex items-center justify-between py-2"><span><Badge tone="info">{e.action}</Badge> <span className="ml-2 text-slate-600 dark:text-slate-300">{e.resource_type} {e.resource_id}</span></span><span className="font-mono text-[11px] text-slate-500">{e.created_at.slice(0, 19).replace("T", " ")}</span></li>)}
            </ul>
          )}
        </Card>
      )}
    </div>
  );
}