import { useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Background, Controls, ReactFlow, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useDocuments, useFindings } from "../../api/hooks";
import { DOC_TYPE_LABEL } from "../../api/types";
import { Card, Empty, PageHeader, Skeleton } from "../../components/ui";

const COLOR: Record<string, string> = { high: "#dc2626", medium: "#d97706", low: "#ca8a04", info: "#94a3b8" };

export default function EvidenceGraph() {
  const id = Number(useParams().caseId);
  const nav = useNavigate();
  const docs = useDocuments(id);
  const findings = useFindings(id);
  const { nodes, edges } = useMemo(() => {
    const ds = docs.data ?? [];
    const n = ds.length || 1;
    const nodes: Node[] = [{ id: "case", position: { x: 400, y: 260 }, data: { label: `Case #${id}` }, style: { background: "#0f2342", color: "white", borderRadius: 8, fontWeight: 600 } }];
    ds.forEach((d, i) => {
      const a = (2 * Math.PI * i) / n;
      nodes.push({ id: `d${d.id}`, position: { x: 400 + 300 * Math.cos(a), y: 260 + 200 * Math.sin(a) }, data: { label: `${DOC_TYPE_LABEL[d.doc_type] ?? d.doc_type}\n${d.original_filename}` }, style: { fontSize: 11, whiteSpace: "pre-wrap", borderRadius: 8, borderColor: d.status === "processed" ? "#1e3a5f" : "#dc2626" } });
    });
    const edges: Edge[] = [];
    const seen = new Set<string>();
    (findings.data ?? []).filter((f) => f.severity !== "info").forEach((f) => {
      const docIds = Array.from(new Set(f.evidence.map((e) => e.document_id)));
      const pairs: [string, string][] = docIds.length >= 2 ? docIds.flatMap((a, i) => docIds.slice(i + 1).map((b) => [`d${a}`, `d${b}`] as [string, string])) : docIds.map((a) => [`d${a}`, "case"] as [string, string]);
      pairs.forEach(([s, t]) => {
        const key = `${f.id}-${s}-${t}`;
        if (seen.has(key)) return;
        seen.add(key);
        edges.push({ id: key, source: s, target: t, label: f.rule_id.split(".")[1], labelStyle: { fontSize: 9 }, style: { stroke: COLOR[f.severity], strokeWidth: f.severity === "high" ? 3 : 2 }, animated: f.severity === "high" });
      });
    });
    return { nodes, edges };
  }, [docs.data, findings.data, id]);
  return (
    <div>
      <PageHeader title="Evidence Graph" subtitle="Documents are nodes; each non-informational finding is an edge between the documents it cites (red = high, amber = medium). Click a document to open it." />
      <Card>
        {docs.isLoading || findings.isLoading ? <Skeleton rows={8} /> : !docs.data?.length ? <Empty title="No documents" /> : (
          <div style={{ height: 560 }}>
            <ReactFlow nodes={nodes} edges={edges} fitView onNodeClick={(_, node) => node.id.startsWith("d") && nav(`../documents/${node.id.slice(1)}`)}>
              <Background /><Controls />
            </ReactFlow>
          </div>
        )}
      </Card>
    </div>
  );
}