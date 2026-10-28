import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api } from "../api/client";
import { useHealth, useRules, useUsers } from "../api/hooks";
import { useAuth } from "../auth";
import { Badge, Card, ErrorBox, PageHeader, useToast } from "../components/ui";

export default function SettingsPage() {
  const { user } = useAuth();
  const health = useHealth();
  const rules = useRules();
  const isAdmin = user?.role === "admin";
  const users = useUsers(isAdmin);
  const qc = useQueryClient();
  const toast = useToast();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("analyst");
  const create = useMutation({
    mutationFn: () => api("/auth/users", { method: "POST", json: { email, password, role } }),
    onSuccess: () => { toast.push("User created", "ok"); setEmail(""); setPassword(""); qc.invalidateQueries({ queryKey: ["users"] }); },
  });
  const caps = health.data?.capabilities ?? {};
  const cloud = [["S3 evidence storage", caps.s3], ["Textract OCR", caps.textract], ["Bedrock assistant", caps.bedrock], ["Local OCR (Tesseract)", caps.ocr], ["Native PDF extraction", caps.native_pdf]];
  return (
    <div>
      <PageHeader title="Settings and cloud status" subtitle="Run mode, capability status, rule catalogue and user administration." />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Runtime">
          <div className="space-y-2 text-sm">
            <div>Run mode <Badge tone="neutral">{health.data?.run_mode ?? "…"}</Badge>, API v{health.data?.version}, {health.data?.rules} rules registered</div>
            <div>Signed in as <strong>{user?.email}</strong> ({user?.role})</div>
            <div className="pt-2 text-xs font-semibold uppercase tracking-wide text-slate-500">AWS / optional services</div>
            {cloud.map(([k, v]) => <div key={String(k)} className="flex items-center justify-between border-t border-slate-100 py-1 dark:border-slate-800"><span>{k}</span><Badge tone={v ? "ok" : "info"}>{v ? "available" : "not configured"}</Badge></div>)}
            <p className="pt-2 text-xs text-slate-500">Everything in AWS mode is marked UNVERIFIED until it has been run in the target account; local processing continues to work when cloud services are unavailable.</p>
          </div>
        </Card>
        <Card title="Rule catalogue">
          <div className="max-h-80 overflow-auto">
            <table className="w-full"><thead><tr><th className="th">Rule</th><th className="th">Engine</th><th className="th">Requires</th></tr></thead>
              <tbody>{(rules.data ?? []).map((r) => <tr key={r.id}><td className="td"><div className="mono">{r.id}</div><div className="text-xs text-slate-500">{r.description}</div></td><td className="td">{r.engine}</td><td className="td text-xs">{r.requires.join(", ") || "any"}</td></tr>)}</tbody></table>
          </div>
        </Card>
        {isAdmin && (
          <Card title="Users (admin)" className="lg:col-span-2">
            <div className="grid gap-6 md:grid-cols-2">
              <table className="w-full"><thead><tr><th className="th">Email</th><th className="th">Role</th><th className="th">Active</th></tr></thead>
                <tbody>{(users.data ?? []).map((u) => <tr key={u.id}><td className="td">{u.email}</td><td className="td"><Badge tone="neutral">{u.role}</Badge></td><td className="td">{u.is_active ? "yes" : "no"}</td></tr>)}</tbody></table>
              <form className="space-y-2" onSubmit={(e: FormEvent) => { e.preventDefault(); create.mutate(); }}>
                <div><label className="label">Email</label><input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></div>
                <div><label className="label">Password (min 10)</label><input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={10} required /></div>
                <div><label className="label">Role</label><select className="input" value={role} onChange={(e) => setRole(e.target.value)}><option>analyst</option><option>reviewer</option><option>viewer</option><option>admin</option></select></div>
                {create.error && <ErrorBox error={create.error} />}
                <button className="btn-primary" disabled={create.isPending}>Create user</button>
                <p className="text-xs text-slate-500">Roles are assigned by admins only; there is no self-registration.</p>
              </form>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}