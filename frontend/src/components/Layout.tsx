import { Link, NavLink, Outlet, useLocation, useMatch } from "react-router-dom";
import { FileSearch, FolderOpen, GitCompare, History, LayoutDashboard, Settings } from "lucide-react";
import { useAuth } from "../auth";
import { useCase, useHealth } from "../api/hooks";

const PRIMARY = [
  { to: "/overview", label: "Overview", icon: LayoutDashboard },
  { to: "/scan", label: "Scan a document", icon: FileSearch },
  { to: "/compare", label: "Compare versions", icon: GitCompare },
  { to: "/cases", label: "Investigations", icon: FolderOpen },
  { to: "/audit", label: "Audit trail", icon: History },
  { to: "/settings", label: "Settings", icon: Settings },
];
const CASE_MAIN = [["summary", "Summary"], ["upload", "Upload"], ["documents", "Documents"], ["findings", "Findings"], ["graph", "Evidence graph"], ["risk", "Risk breakdown"], ["reports", "Report"]];
const CASE_MORE = [["forensics", "Forensics"], ["assistant", "Assistant"], ["vault", "Evidence vault"], ["audit", "Audit"]];

function RailLink({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink to={to} className={({ isActive }) => `group relative flex items-center gap-2.5 py-[7px] pl-6 pr-4 text-[15px] transition-colors duration-150 ${isActive ? "font-medium text-fg" : "text-fg2 hover:text-fg"}`}>
      {({ isActive }) => <><span className={`absolute left-0 top-1/2 h-4 w-[3px] -translate-y-1/2 bg-accent transition-opacity duration-150 ${isActive ? "opacity-100" : "opacity-0"}`} />{children}</>}
    </NavLink>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  const health = useHealth();
  const loc = useLocation();
  const m = useMatch("/cases/:caseId/*");
  const caseId = m?.params.caseId && /^\d+$/.test(m.params.caseId) ? Number(m.params.caseId) : NaN;
  const cs = useCase(caseId);
  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-[232px] shrink-0 flex-col border-r border-line bg-side md:flex">
        <Link to="/overview" className="px-6 pb-6 pt-6">
          <span className="font-display text-[19px] font-semibold leading-none tracking-tight text-fg">Doc<span className="text-accent">Sentry</span></span>
          <span className="mt-1.5 block text-xs text-muted">Digital evidence desk</span>
        </Link>
        <nav>{PRIMARY.map((n) => <RailLink key={n.to} to={n.to}><n.icon className="h-4 w-4 opacity-70 transition-opacity group-hover:opacity-100" />{n.label}</RailLink>)}</nav>
        {Number.isFinite(caseId) && (
          <div className="mt-6 border-t border-line pt-4">
            <div className="px-6 text-xs text-muted">Investigation</div>
            <div className="truncate px-6 pb-2 pt-1 text-sm font-medium text-fg" title={cs.data?.title}>{cs.data?.title ?? "..."}</div>
            <nav>{CASE_MAIN.map(([to, label]) => <RailLink key={to} to={`/cases/${caseId}/${to}`}>{label}</RailLink>)}</nav>
            <div className="mt-4 px-6 pb-1 text-xs text-muted">More</div>
            <nav>{CASE_MORE.map(([to, label]) => <RailLink key={to} to={`/cases/${caseId}/${to}`}>{label}</RailLink>)}</nav>
          </div>
        )}
        <div className="mt-auto px-6 py-4 font-mono text-[11px] text-muted">{health.data ? <>{health.data.run_mode} / api {health.data.version} / ocr {health.data.capabilities.ocr_engine ?? "off"}</> : "connecting..."}</div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-line bg-fog px-6 py-2">
          <div className="text-sm text-fg2">
            {Number.isFinite(caseId) ? <><Link to="/cases" className="transition-colors hover:text-fg">Investigations</Link><span className="mx-2 text-muted">/</span><span className="text-fg">{cs.data?.title ?? `Case ${caseId}`}</span></> : <Link to="/" className="font-display font-semibold text-fg md:hidden">DocSentry</Link>}
          </div>
          <div className="flex items-center gap-3 text-sm">
            {user && <span className="hidden text-fg2 sm:inline">{user.email} <span className="text-muted">({user.role})</span></span>}
            <Link to="/" className="btn-secondary">Product page</Link>
            <button className="btn-secondary" onClick={logout}>Sign out</button>
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1240px] flex-1 px-6 py-7"><div key={loc.pathname} className="animate-fade"><Outlet /></div></main>
      </div>
    </div>
  );
}