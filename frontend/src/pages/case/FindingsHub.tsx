import { useState } from "react";
import { useParams } from "react-router-dom";
import { useFindings } from "../../api/hooks";
import { PageHeader, Skeleton } from "../../components/ui";
import { FindingsList } from "./Findings";

const TABS = [["all", "All"], ["cross_document", "Cross-document"], ["identity", "Identity"], ["financial", "Financial"]] as const;

export default function FindingsHub() {
  const id = Number(useParams().caseId);
  const [tab, setTab] = useState<string>("all");
  const [showInfo, setShowInfo] = useState(false);
  const q = useFindings(id);
  const list = (q.data ?? []).filter((f) => (tab === "all" || f.engine === tab) && (showInfo || f.severity !== "info"));
  return (
    <div>
      <PageHeader title="Findings" subtitle="Every finding cites the document, field and page it came from. Severity drives the score; informational findings are the checks that passed." />
      <div className="mb-5 flex flex-wrap items-center gap-2">
        {TABS.map(([k, label]) => <button key={k} className={`chip ${tab === k ? "border-accent-500 bg-accent-50 text-accent-700 dark:bg-ink-700" : ""}`} onClick={() => setTab(k)}>{label}</button>)}
        <label className="ml-auto flex items-center gap-2 text-sm text-slate-600"><input type="checkbox" checked={showInfo} onChange={(e) => setShowInfo(e.target.checked)} /> Show passed checks</label>
      </div>
      {q.isLoading ? <Skeleton rows={6} /> : <FindingsList findings={list} emptyHint={showInfo ? "Run the analysis from the Summary page." : "No discrepancies in this group. Tick 'Show passed checks' to see what was verified."} />}
    </div>
  );
}