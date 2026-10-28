import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Case } from "../api/types";
import { Card, ErrorBox, PageHeader, useToast } from "../components/ui";

export default function CreateCase() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const [title, setTitle] = useState("");
  const [type, setType] = useState("loan_investigation");
  const [desc, setDesc] = useState("");
  const scenarios = useQuery({ queryKey: ["scenarios"], queryFn: () => api<{ id: number; name: string }[]>("/demo/scenarios") });
  const create = useMutation({
    mutationFn: () => api<Case>("/cases", { method: "POST", json: { title, case_type: type, description: desc } }),
    onSuccess: (c) => { qc.invalidateQueries({ queryKey: ["cases"] }); nav(`/cases/${c.id}/upload`); },
  });
  const demo = useMutation({
    mutationFn: (id: number) => api<Case>(`/demo/scenarios/${id}`, { method: "POST" }),
    onSuccess: (c) => { qc.invalidateQueries({ queryKey: ["cases"] }); toast.push(`Demo case created: ${c.risk_outcome}`, "ok"); nav(`/cases/${c.id}/risk`); },
    onError: (e: Error) => toast.push(e.message, "error"),
  });
  const submit = (e: FormEvent) => { e.preventDefault(); create.mutate(); };
  return (
    <div>
      <PageHeader title="Create case" />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="New investigation">
          <form onSubmit={submit} className="space-y-3">
            <div><label className="label">Title</label><input className="input" value={title} onChange={(e) => setTitle(e.target.value)} minLength={3} required placeholder="Personal Loan Investigation – R. Sharma" /></div>
            <div><label className="label">Case type</label>
              <select className="input" value={type} onChange={(e) => setType(e.target.value)}>
                <option value="loan_investigation">Loan investigation</option><option value="kyc">KYC review</option><option value="vendor_audit">Vendor / invoice audit</option><option value="general">General</option>
              </select></div>
            <div><label className="label">Description</label><textarea className="input" rows={3} value={desc} onChange={(e) => setDesc(e.target.value)} /></div>
            {create.error && <ErrorBox error={create.error} />}
            <button className="btn-primary" disabled={create.isPending}>{create.isPending ? "Creating…" : "Create case"}</button>
          </form>
        </Card>
        <Card title="Demo scenarios (synthetic documents, same pipeline)">
          <p className="mb-3 text-xs text-slate-500">Each scenario renders fresh synthetic PDFs, uploads them with generic filenames and runs the standard pipeline. Nothing is keyed on a filename; the findings are computed from the document content.</p>
          <div className="space-y-2">
            {(scenarios.data ?? []).map((s) => (
              <div key={s.id} className="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2 dark:border-slate-800">
                <div className="text-sm"><span className="mr-2 font-mono text-xs text-slate-500">#{s.id}</span>{s.name}</div>
                <button className="btn-secondary" disabled={demo.isPending} onClick={() => demo.mutate(s.id)}>{demo.isPending && demo.variables === s.id ? "Generating…" : "Create"}</button>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}