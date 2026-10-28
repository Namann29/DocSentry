import { Link } from "react-router-dom";
import { useHealth } from "../api/hooks";
import { PageHeader, Unavailable } from "../components/ui";

export default function Compare() {
  const health = useHealth();
  const available = health.data?.capabilities?.compare === true;
  return (
    <div>
      <PageHeader title="Compare two versions" subtitle="Word-level comparison of two versions of the same document, with changed numeric values listed first." />
      {!available && <Unavailable feature="Version comparison" reason="The comparison endpoint is not part of this build. Nothing is simulated here. For salary slip against bank statement, use the Investigate workspace." />}
      <div className="mt-6 grid gap-4 md:grid-cols-2">
        {["Original version", "Comparison version"].map((label) => (
          <div key={label} className="card p-5 opacity-60"><div className="eyebrow">{label}</div><div className="mt-3 rounded-lg border border-dashed border-slate-300 px-4 py-6 text-center text-sm text-slate-500 dark:border-ink-600">Available once comparison is built</div></div>
        ))}
      </div>
      <div className="mt-4"><Link className="btn-secondary" to="/investigate">Open salary slip vs bank statement</Link></div>
    </div>
  );
}