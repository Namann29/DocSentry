import { Link } from "react-router-dom";
import { Lightbulb } from "lucide-react";

export function Explain({ title = "What this demonstrates", points }: { title?: string; points: string[] }) {
  return (
    <aside className="flex gap-3 border-l-2 border-accent bg-surface2 px-4 py-3 text-[15px]">
      <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
      <div><div className="font-medium">{title}</div><ul className="mt-1 list-disc space-y-0.5 pl-4 text-fg2">{points.map((p) => <li key={p}>{p}</li>)}</ul></div>
    </aside>
  );
}

const FEATURES: { title: string; what: string; where: string; to: string }[] = [
  { title: "Upload validation", what: "File type is read from the first bytes, not the name. Launch actions rejected; JavaScript and embedded files flagged; passwords used in memory only.", where: "Scan a document", to: "/scan" },
  { title: "Text extraction and table reconstruction", what: "PyMuPDF gives every word with coordinates; a geometry algorithm finds the header row and rebuilds bank-statement tables across layouts.", where: "Any document, Extraction review", to: "/cases" },
  { title: "Modification indicators", what: "Numbers set in a different font family than the page, and files saved over themselves. Reported as potential, never as proof.", where: "Scan result, document viewer", to: "/scan" },
  { title: "Sensitive-information detection", what: "PAN, Aadhaar (Verhoeff checksum), GSTIN, IFSC, account, phone and email found by pattern; shown masked, never stored unmasked.", where: "Scan result", to: "/scan" },
  { title: "Cross-document investigation", what: "Rules compare documents with each other: salary slip vs bank credit, invoice vs purchase order vs payment, name and date of birth across identity documents.", where: "Case summary, Findings", to: "/investigate" },
  { title: "Explainable risk score", what: "Fixed points by severity under a versioned policy, halved for low-confidence extraction; every point is listed. Too few checks gives 'Insufficient evidence'.", where: "Risk breakdown", to: "/cases" },
  { title: "Tamper-evident audit log", what: "Append-only, hash-chained events with a database trigger; the chain can be re-verified on demand.", where: "Audit trail", to: "/audit" },
  { title: "Evidence-linked PDF report", what: "Hashes, findings by verification level, risk contributions, security scan, timeline and a limitations section.", where: "Case report", to: "/cases" },
];

export function FeatureHighlights() {
  return (
    <section>
      <div className="flex items-baseline justify-between"><h2 className="font-display text-lg font-semibold">What to look at</h2><span className="text-xs text-muted">Each item links to the screen that shows it</span></div>
      <ol className="mt-3 grid gap-x-8 gap-y-3 md:grid-cols-2">
        {FEATURES.map((f, i) => (
          <li key={f.title} className="grid grid-cols-[1.6rem_1fr] gap-2 border-t border-line py-3">
            <span className="font-mono text-xs text-muted">{String(i + 1).padStart(2, "0")}</span>
            <div><Link to={f.to} className="font-medium hover:text-accent">{f.title}</Link><p className="mt-0.5 text-sm text-fg2">{f.what}</p><p className="mt-0.5 text-xs text-muted">See: {f.where}</p></div>
          </li>
        ))}
      </ol>
    </section>
  );
}