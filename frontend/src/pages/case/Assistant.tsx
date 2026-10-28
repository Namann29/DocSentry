import { useParams } from "react-router-dom";
import { useHealth } from "../../api/hooks";
import { Card, PageHeader, Unavailable } from "../../components/ui";

export default function Assistant() {
  const { caseId } = useParams();
  const health = useHealth();
  return (
    <div>
      <PageHeader title="AI Assistant" subtitle="Evidence-grounded question answering over this case's documents, with citations to document and page." />
      <Unavailable feature="AI Assistant" reason={`Local retrieval (FAISS) and the optional Bedrock backend are not yet built in this version (capabilities: rag=${String(health.data?.capabilities?.rag ?? false)}). When available it answers only from case evidence, cites document and page, never overrides deterministic findings, and treats document text as untrusted input. No external AI service is called without explicit configuration and consent.`} />
      <Card className="mt-4" title={`Case #${caseId}`}>
        <div className="flex gap-2">
          <input className="input" disabled placeholder="Ask about this case (unavailable in this build)" />
          <button className="btn-primary" disabled>Ask</button>
        </div>
        <p className="mt-2 text-xs text-slate-500">This control is disabled rather than simulated: there is no model behind it yet.</p>
      </Card>
    </div>
  );
}