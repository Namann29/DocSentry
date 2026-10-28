import { useParams } from "react-router-dom";
import { useDocuments, useDocument } from "../../api/hooks";
import type { Doc } from "../../api/types";
import { Badge, Card, Empty, PageHeader, Skeleton, Unavailable } from "../../components/ui";

function Row({ d, dupOf }: { d: Doc; dupOf?: string }) {
  const detail = useDocument(d.id);
  const m = detail.data?.pdf_metadata ?? {};
  return (
    <tr>
      <td className="td font-medium">{d.original_filename}</td>
      <td className="td mono break-all">{d.sha256}</td>
      <td className="td text-xs">{m.producer || m.creator || "-"}<br /><span className="text-slate-500">{m.creationDate ? `created ${m.creationDate}` : ""}{m.modDate && m.modDate !== m.creationDate ? `, modified ${m.modDate}` : ""}</span></td>
      <td className="td">{d.security_flags.map((f) => <Badge key={f} tone="warn">{f}</Badge>)}{dupOf && <Badge tone="medium">exact duplicate of {dupOf}</Badge>}{!d.security_flags.length && !dupOf && <Badge tone="ok">no flags</Badge>}</td>
    </tr>
  );
}

export default function Forensics() {
  const id = Number(useParams().caseId);
  const docs = useDocuments(id);
  const byHash = new Map<string, string>();
  const dup = new Map<number, string>();
  (docs.data ?? []).forEach((d) => { if (byHash.has(d.sha256)) dup.set(d.id, byHash.get(d.sha256)!); else byHash.set(d.sha256, d.original_filename); });
  return (
    <div>
      <PageHeader title="Document forensics" subtitle="SHA-256 fingerprints, PDF metadata, risky PDF features (JavaScript, embedded files, open actions) and exact duplicates. All indicators are heuristics: potential anomalies, never proof of manipulation." />
      <div className="mb-4"><Unavailable feature="Advanced forensics (near-duplicate perceptual hashing, error-level analysis, incremental-update and version comparison)" reason="Planned for the forensics batch; this page currently shows fingerprint, metadata and structural flags computed at upload." /></div>
      <Card>
        {docs.isLoading ? <Skeleton /> : !docs.data?.length ? <Empty title="No documents" /> : (
          <table className="w-full"><thead><tr><th className="th">File</th><th className="th">SHA-256</th><th className="th">Producer / dates</th><th className="th">Indicators</th></tr></thead>
            <tbody>{docs.data.map((d) => <Row key={d.id} d={d} dupOf={dup.get(d.id)} />)}</tbody></table>
        )}
      </Card>
    </div>
  );
}