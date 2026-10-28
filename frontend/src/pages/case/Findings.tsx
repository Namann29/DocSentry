import { Link, useParams } from "react-router-dom";
import { useFindings } from "../../api/hooks";
import type { Finding } from "../../api/types";
import { LEVEL_NAMES } from "../../api/types";
import { Badge, Empty, ErrorBox, PageHeader, Skeleton } from "../../components/ui";

const BAR: Record<string, string> = { high: "border-red-600", medium: "border-amber-500", low: "border-yellow-400", info: "border-slate-300 dark:border-ink-600" };

export function FindingCard({ f }: { f: Finding }) {
  return (
    <article className={`border-l-2 ${BAR[f.severity]} bg-white px-4 py-3 dark:bg-ink-800`}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-xs text-slate-500">
        <Badge tone={f.severity}>{f.severity}</Badge>
        <span>Level {f.level}, {LEVEL_NAMES[f.level].toLowerCase()}</span>
        {f.possible_extraction_error && <Badge tone="warn">possible extraction error, points halved</Badge>}
        <span className="ml-auto tabular-nums">{f.points} points</span>
      </div>
      <h3 className="mt-1 font-medium leading-snug">{f.title}</h3>
      {f.explanation && <p className="mt-1 max-w-3xl text-sm text-slate-600 dark:text-slate-300">{f.explanation}</p>}
      {f.evidence.length > 0 && (
        <dl className="mt-2 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
          {f.evidence.map((e, i) => (
            <div key={i} className="flex gap-2">
              <dt className="shrink-0 text-slate-500">{e.filename}</dt>
              <dd className="min-w-0 truncate">
                <Link className="link" to={`../documents/${e.document_id}${e.page ? `?page=${e.page}&field=${encodeURIComponent(e.field)}` : ""}`}>{e.field}</Link>
                {e.value != null && <span className="text-slate-700 dark:text-slate-200"> = {String(e.value).slice(0, 48)}</span>}
                {e.page ? <span className="text-slate-400"> p.{e.page}</span> : null}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </article>
  );
}

export function FindingsList({ findings, emptyHint }: { findings: Finding[]; emptyHint: string }) {
  if (findings.length === 0) return <Empty title="No findings" hint={emptyHint} />;
  const groups = ["high", "medium", "low", "info"] as const;
  return (
    <div className="space-y-8">
      {groups.map((g) => {
        const items = findings.filter((f) => f.severity === g);
        return items.length ? (
          <section key={g}>
            <h2 className="mb-2 text-sm font-semibold">{g === "info" ? "Informational" : `${g[0].toUpperCase()}${g.slice(1)} severity`} <span className="font-normal text-slate-500">({items.length})</span></h2>
            <div className="stagger divide-y divide-slate-100 border-y border-slate-200 dark:divide-ink-700 dark:border-ink-700">{items.map((f) => <FindingCard key={f.id} f={f} />)}</div>
          </section>
        ) : null;
      })}
    </div>
  );
}

export default function FindingsPage({ engine, title, subtitle }: { engine: string; title: string; subtitle: string }) {
  const id = Number(useParams().caseId);
  const q = useFindings(id, engine);
  return (
    <div>
      <PageHeader title={title} subtitle={subtitle} />
      {q.error && <ErrorBox error={q.error} />}
      {q.isLoading ? <Skeleton rows={6} /> : <FindingsList findings={q.data ?? []} emptyHint="Run processing from the Upload section. Findings appear once the relevant document types are present." />}
    </div>
  );
}