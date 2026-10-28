import { useParams } from "react-router-dom";
import { useRisk } from "../../api/hooks";
import { Badge, Card, ErrorBox, PageHeader, Skeleton, Stat, outcomeTone } from "../../components/ui";
import { Explain } from "../../components/Explain";

export default function RiskPage() {
  const id = Number(useParams().caseId);
  const r = useRisk(id);
  if (r.isLoading) return <Skeleton rows={8} />;
  if (r.error || !r.data) return <ErrorBox error={r.error ?? "No risk data"} />;
  const b = r.data.breakdown ?? {};
  const contributions: any[] = (b.contributions ?? []).filter((c: any) => c.points > 0 || c.severity !== "info");
  const checks: any[] = b.checks ?? [];
  const evaluated = checks.filter((c) => c.status === "evaluated").length;
  const applicable = checks.filter((c) => c.status !== "not_applicable").length;
  return (
    <div>
      <PageHeader title="Risk assessment" subtitle={`Policy ${b.policy_version ?? "?"}: each finding contributes fixed points by severity (${Object.entries(b.points_table ?? {}).map(([k, v]) => `${k} ${v}`).join(", ")}), halved when the involved fields have low extraction confidence. Review from ${b.thresholds?.review ?? 15} points, high from ${b.thresholds?.high ?? 50}. The outcome is a recommendation, not a fraud judgement.`} />
      <div className="mb-6"><Explain points={["No model produces this number. Points are fixed by severity, halved when an involved field has low extraction confidence, and capped at 100.", "The checks table shows what ran, what did not apply, and that verification with the issuing authority was not performed.", "Outcome thresholds are part of the policy and versioned, so a reviewer can see exactly why a case landed where it did."]} /></div>
      <div className="mb-8 grid grid-cols-2 gap-6 md:grid-cols-4">
        <Stat label="Outcome" value={<Badge tone={outcomeTone(r.data.outcome)}>{r.data.outcome}</Badge>} />
        <Stat label="Points" value={`${r.data.score}`} hint={`${b.raw_points ?? 0} before the cap of 100`} />
        <Stat label="Evidence coverage" value={`${Math.round(r.data.evidence_coverage * 100)}%`} hint={`${evaluated} of ${applicable} applicable checks evaluated`} />
        <Stat label="Extraction quality" value={r.data.extraction_quality.toFixed(2)} hint="mean confidence of extracted fields" />
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <Card title="Contributions">
          {contributions.length === 0 ? <div className="text-sm text-slate-500">No finding contributes points.</div> : (
            <table>
              <thead><tr><th className="th">Finding</th><th className="th">Severity</th><th className="th num">Points</th></tr></thead>
              <tbody>{contributions.map((c, i) => <tr key={i}><td className="td"><div>{c.title}</div><div className="text-xs text-slate-500">{c.rule_id}, level {c.level}</div></td><td className="td"><Badge tone={c.severity}>{c.severity}</Badge></td><td className="td num">{c.points}{c.extraction_discounted && <div className="text-xs text-slate-500">halved</div>}</td></tr>)}</tbody>
            </table>
          )}
        </Card>
        <Card title="Checks">
          <table>
            <thead><tr><th className="th">Check</th><th className="th">Status</th><th className="th num">Findings</th></tr></thead>
            <tbody>
              {checks.map((c) => <tr key={c.rule_id}><td className="td"><div>{c.description || c.rule_id}</div><div className="text-xs text-slate-500">{c.rule_id}</div></td><td className="td"><Badge tone={c.status === "evaluated" ? "ok" : c.status === "error" ? "high" : "info"}>{c.status.replace("_", " ")}</Badge></td><td className="td num">{c.findings}</td></tr>)}
              <tr><td className="td"><div>Verification with the issuing authority (PAN, Aadhaar, GSTIN, bank)</div><div className="text-xs text-slate-500">external.authoritative_verification</div></td><td className="td"><Badge tone="warn">not performed</Badge></td><td className="td num">–</td></tr>
            </tbody>
          </table>
        </Card>
      </div>
      <p className="mt-6 max-w-3xl text-sm text-slate-500">{(b.notes ?? []).join(" ")}</p>
    </div>
  );
}