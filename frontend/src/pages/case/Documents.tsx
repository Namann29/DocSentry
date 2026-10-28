import { Link, useParams } from "react-router-dom";
import { useDocuments, useStats } from "../../api/hooks";
import { DOC_TYPE_LABEL } from "../../api/types";
import { Badge, Card, Empty, PageHeader, Skeleton, Stat, statusTone } from "../../components/ui";

export default function Documents() {
  const id = Number(useParams().caseId);
  const docs = useDocuments(id);
  const stats = useStats(id);
  return (
    <div>
      <PageHeader title="Documents" subtitle="Classification, extraction method and quality for each document. Open a document to view evidence highlights or correct fields." />
      <div className="mb-6 grid gap-4 md:grid-cols-4">
        <Stat label="Documents" value={docs.data?.length ?? "…"} />
        <Stat label="Extracted fields" value={stats.data?.fields ?? "…"} />
        <Stat label="Mean confidence" value={stats.data ? stats.data.mean_confidence.toFixed(2) : "…"} />
        <Stat label="Correction rate" value={stats.data ? `${(stats.data.correction_rate * 100).toFixed(1)}%` : "…"} hint={`${stats.data?.corrected ?? 0} manual corrections`} />
      </div>
      <Card>
        {docs.isLoading ? <Skeleton /> : !docs.data?.length ? <Empty title="No documents" /> : (
          <table className="w-full">
            <thead><tr><th className="th">File</th><th className="th">Classified as</th><th className="th">Method</th><th className="th">Status</th><th className="th">Actions</th></tr></thead>
            <tbody>
              {docs.data.map((d) => (
                <tr key={d.id}>
                  <td className="td font-medium">{d.original_filename}</td>
                  <td className="td">{DOC_TYPE_LABEL[d.doc_type] ?? d.doc_type} <span className="text-xs text-slate-500">({d.classification_confidence.toFixed(2)})</span></td>
                  <td className="td mono">{d.extraction_method}</td>
                  <td className="td"><Badge tone={statusTone(d.status)}>{d.status}</Badge></td>
                  <td className="td space-x-2"><Link className="underline" to={`${d.id}`}>Viewer</Link><Link className="underline" to={`../review/${d.id}`}>Extraction review</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}