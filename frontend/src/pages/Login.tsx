import { useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { useAuth } from "../auth";
import { ErrorBox } from "../components/ui";

const LEVELS = [
  ["Format validation", "The value is well-formed."],
  ["Internal consistency", "The document agrees with itself."],
  ["Cross-document consistency", "The documents agree with each other."],
  ["Cryptographic verification", "A signature verifies against a trusted certificate."],
  ["External authoritative verification", "Confirmed by the issuing authority. Not performed in this build."],
  ["Suspicious indicator", "A heuristic flag or an item nobody has checked yet."],
];

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const loc = useLocation() as { state?: { from?: string } };
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      nav(loc.state?.from || "/overview", { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <section className="hidden flex-col justify-between bg-surface p-10 text-fg2 lg:flex">
        <div className="flex items-center gap-2 text-fg"><ShieldCheck className="h-6 w-6" /><span className="text-lg font-semibold">DocSentry</span></div>
        <div className="max-w-lg">
          <h1 className="text-3xl font-semibold leading-tight text-fg">Every check says exactly how much it proves.</h1>
          <p className="mt-3 text-fg2">Upload the documents of a case, and DocSentry extracts them, compares them with each other and reports what it found, at one of six levels of verification.</p>
          <ol className="mt-8 divide-y divide-line border-y border-line">
            {LEVELS.map(([name, desc], i) => (
              <li key={name} className="grid grid-cols-[2rem_1fr] gap-3 py-2.5">
                <span className="tabular-nums text-muted">{i + 1}</span>
                <span><span className="text-fg">{name}</span><span className="block text-sm text-muted">{desc}</span></span>
              </li>
            ))}
          </ol>
        </div>
        <p className="text-xs text-muted">A well-formed identifier is not an authentic document. Outcomes are investigation recommendations, not fraud judgements.</p>
      </section>
      <section className="flex items-center justify-center p-8">
        <form onSubmit={submit} className="w-full max-w-sm">
          <div className="mb-8 lg:hidden"><div className="flex items-center gap-2"><ShieldCheck className="h-6 w-6" /><span className="text-lg font-semibold">DocSentry</span></div></div>
          <h2 className="text-xl font-semibold">Sign in</h2>
          <p className="mb-6 mt-1 text-sm text-slate-500">Use the account an administrator created for you.</p>
          <label className="label" htmlFor="email">Email</label>
          <input id="email" className="input mb-4" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus autoComplete="username" />
          <label className="label" htmlFor="password">Password</label>
          <input id="password" className="input mb-5" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
          {error ? <div className="mb-4"><ErrorBox error={error} /></div> : null}
          <button className="btn-primary w-full justify-center" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
          <p className="mt-6 text-xs text-slate-500">For local development the first administrator comes from ADMIN_EMAIL and ADMIN_PASSWORD in backend/.env.</p>
        </form>
      </section>
    </div>
  );
}