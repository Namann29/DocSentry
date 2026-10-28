import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowDown, FileSearch, FileText, GitCompare, History, ScanSearch, Scale, ShieldAlert } from "lucide-react";
import { useAuth } from "../auth";

/* ---------- small helpers ---------- */
function useVisible<T extends HTMLElement>(threshold = 0.15) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { el.classList.add("is-visible"); io.disconnect(); } }, { threshold });
    io.observe(el);
    return () => io.disconnect();
  }, [threshold]);
  return ref;
}

function Reveal({ children, className = "", slow = false }: { children: ReactNode; className?: string; slow?: boolean }) {
  const ref = useVisible<HTMLDivElement>();
  return <div ref={ref} className={`${slow ? "reveal-slow" : "reveal"} ${className}`}>{children}</div>;
}

function Rule({ className = "" }: { className?: string }) {
  const ref = useVisible<HTMLDivElement>(0.5);
  return <div ref={ref} className={`draw-x h-px w-full bg-line ${className}`} />;
}

function ScrollProgress() {
  const [p, setP] = useState(0);
  useEffect(() => {
    const onScroll = () => { const h = document.documentElement; const max = h.scrollHeight - h.clientHeight; setP(max > 0 ? h.scrollTop / max : 0); };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return <div className="fixed left-0 top-0 z-30 h-[2px] bg-accent transition-[width] duration-150" style={{ width: `${p * 100}%` }} aria-hidden />;
}

/* ---------- hero illustration (decorative, annotated) ---------- */
function Evidence() {
  const box = useRef<HTMLDivElement>(null);
  const onMove = (e: React.MouseEvent) => {
    const el = box.current; if (!el) return;
    const r = el.getBoundingClientRect();
    el.style.setProperty("--mx", `${((e.clientX - r.left) / r.width) * 100}%`);
    el.style.setProperty("--my", `${((e.clientY - r.top) / r.height) * 100}%`);
  };
  return (
    <div ref={box} onMouseMove={onMove} className="hero-spot relative mx-auto w-full max-w-[460px] rounded-md p-4" aria-hidden>
      <div className="relative">
        <svg viewBox="0 0 420 460" className="h-auto w-full" fill="none">
          <path d="M60 24h210l70 70v330a10 10 0 0 1-10 10H60a10 10 0 0 1-10-10V34a10 10 0 0 1 10-10z" stroke="rgb(var(--line))" strokeWidth="1.5" fill="rgb(var(--surface))" />
          <path d="M270 24v60a10 10 0 0 0 10 10h60" stroke="rgb(var(--line))" strokeWidth="1.5" />
          {[120, 148, 176, 204].map((y, i) => <line key={y} x1="84" y1={y} x2={i === 1 ? 240 : i === 3 ? 262 : 300} y2={y} stroke="rgb(var(--fg2))" strokeOpacity="0.5" strokeWidth="1.5" />)}
          <rect x="84" y="236" width="236" height="26" rx="3" stroke="rgb(var(--line))" strokeWidth="1.2" />
          <rect x="214" y="241" width="96" height="16" rx="2" fill="rgb(var(--sev-warn) / 0.18)" stroke="rgb(var(--sev-warn))" strokeWidth="1.3" />
          <circle cx="372" cy="249" r="4.5" fill="rgb(var(--sev-warn))" />
          <line x1="310" y1="249" x2="367" y2="249" stroke="rgb(var(--sev-warn))" strokeWidth="1" strokeDasharray="3 3" />
          {[296, 324].map((y) => <line key={y} x1="84" y1={y} x2="280" y2={y} stroke="rgb(var(--fg2))" strokeOpacity="0.5" strokeWidth="1.5" />)}
          <rect x="84" y="352" width="150" height="18" rx="2" stroke="rgb(var(--line))" strokeWidth="1.2" />
          <text x="90" y="365" fontSize="10" fill="rgb(var(--muted))" fontFamily="IBM Plex Mono, monospace">XXXX XXXX 1234</text>
          <circle cx="372" cy="361" r="4.5" fill="rgb(var(--accent))" />
          <line x1="234" y1="361" x2="367" y2="361" stroke="rgb(var(--accent))" strokeWidth="1" strokeDasharray="3 3" />
          <line x1="60" y1="424" x2="340" y2="424" stroke="rgb(var(--line))" strokeWidth="1" />
          <text x="84" y="412" fontSize="10" fill="rgb(var(--muted))" fontFamily="IBM Plex Mono, monospace">sha256  9f1c...7e2a</text>
        </svg>
        <div className="scan-occasional pointer-events-none absolute left-[12%] right-[12%] h-px bg-accent/80" />
        <span className="absolute -left-2 top-[8%] font-mono text-[10px] tracking-wide text-muted">DOCUMENT STRUCTURE</span>
        <span className="absolute -right-2 top-[48%] font-mono text-[10px] tracking-wide text-amber-500">FONT ANALYSIS</span>
        <span className="absolute -right-2 top-[76%] font-mono text-[10px] tracking-wide text-accent">MASKED IDENTIFIER</span>
        <span className="absolute left-[18%] bottom-[2%] font-mono text-[10px] tracking-wide text-muted">SHA-256</span>
      </div>
      <p className="mt-2 text-center font-mono text-[10px] text-muted">illustration only; not a scan result</p>
    </div>
  );
}

/* ---------- content ---------- */
const FEATURES = [
  { icon: ScanSearch, n: "01", tag: "STRUCTURE", title: "Document security analysis", text: "Inspect PDF structure, re-saves after creation, metadata dates and producer, and active content such as JavaScript or embedded files.", note: "Every row says what was checked and what could not be." },
  { icon: ShieldAlert, n: "02", tag: "MODIFICATION", title: "Modification indicators", text: "Flag numeric values set in a font family different from the page, and other structural indicators. Reported as potential, never as proof.", note: "Amber in the viewer, tied to page coordinates." },
  { icon: FileSearch, n: "03", tag: "EXPOSURE", title: "Sensitive information detection", text: "Find PAN, Aadhaar, GSTIN, IFSC, account, phone and email identifiers by pattern and checksum. Results are shown masked.", note: "Unmasked values are not stored." },
  { icon: GitCompare, n: "04", tag: "CROSS-DOCUMENT", title: "Cross-document investigation", text: "Compare a salary slip with the bank credit, an invoice with its purchase order and payment, and identity details across documents.", note: "Rules declare the documents they need." },
  { icon: Scale, n: "05", tag: "SCORING", title: "Explainable risk scoring", text: "A versioned points table by severity. Every contribution is listed; too little evidence yields insufficient evidence, not low risk.", note: "No model decides the score." },
  { icon: FileText, n: "06", tag: "REPORT", title: "Investigation reports", text: "Export findings, document fingerprints, the security scan, the score breakdown and a limitations statement as a PDF.", note: "Generated from the case as it stands." },
  { icon: History, n: "07", tag: "AUDIT", title: "Audit history", text: "Uploads, views, downloads, corrections and processing runs are recorded in an append-only, hash-linked log.", note: "Tamper-evident, re-verifiable on demand." },
];

const STEPS = [
  { n: "01", title: "Submit a document", text: "Upload a PDF or an image through the workspace. The type is verified from the file's bytes; passwords are used in memory only." },
  { n: "02", title: "Examine the evidence", text: "Native text is read with word coordinates; photos and scans go through OCR with a quality gate. Metadata, structure, fonts and rule-based checks run." },
  { n: "03", title: "Review the findings", text: "Inspect each indicator with its page and field, read how the score was built, record a review outcome and export the report." },
];

function StepVisual({ step }: { step: number }) {
  return (
    <svg viewBox="0 0 320 220" className="h-auto w-full" fill="none" aria-hidden>
      <rect x="20" y="20" width="280" height="180" rx="6" stroke="rgb(var(--line))" strokeWidth="1.2" fill="rgb(var(--surface))" />
      {step === 0 && <>
        <rect x="60" y="60" width="200" height="100" rx="4" stroke="rgb(var(--accent))" strokeDasharray="5 5" strokeWidth="1.2" />
        <text x="160" y="112" textAnchor="middle" fontSize="11" fill="rgb(var(--fg2))" fontFamily="IBM Plex Mono, monospace">drop file  /  verify bytes</text>
      </>}
      {step === 1 && <>
        {[62, 84, 106, 128, 150].map((y, i) => <line key={y} x1="50" y1={y} x2={i === 2 ? 180 : 250} y2={y} stroke="rgb(var(--fg2))" strokeOpacity="0.5" strokeWidth="1.5" />)}
        <rect x="150" y="100" width="60" height="12" rx="2" fill="rgb(var(--sev-warn) / 0.2)" stroke="rgb(var(--sev-warn))" strokeWidth="1.2" />
        <text x="50" y="180" fontSize="10" fill="rgb(var(--muted))" fontFamily="IBM Plex Mono, monospace">words + coordinates + confidence</text>
      </>}
      {step === 2 && <>
        <circle cx="90" cy="110" r="38" stroke="rgb(var(--line))" strokeWidth="8" />
        <path d="M90 72 a38 38 0 1 1 -27 65" stroke="rgb(var(--sev-ok))" strokeWidth="8" strokeLinecap="round" />
        {[80, 104, 128].map((y, i) => <g key={y}><circle cx="160" cy={y} r="3" fill={i === 0 ? "rgb(var(--sev-warn))" : "rgb(var(--fg2))"} /><line x1="172" y1={y} x2={i === 1 ? 240 : 280} y2={y} stroke="rgb(var(--fg2))" strokeOpacity="0.5" strokeWidth="1.5" /></g>)}
        <text x="150" y="180" fontSize="10" fill="rgb(var(--muted))" fontFamily="IBM Plex Mono, monospace">points by rule  /  report.pdf</text>
      </>}
    </svg>
  );
}

function HowItWorks() {
  const [active, setActive] = useState(0);
  const refs = [useRef<HTMLLIElement>(null), useRef<HTMLLIElement>(null), useRef<HTMLLIElement>(null)];
  const lineRef = useVisible<HTMLDivElement>(0.2);
  useEffect(() => {
    const ios = refs.map((r, i) => {
      const el = r.current; if (!el) return null;
      const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setActive(i); el.classList.add("is-visible"); } }, { threshold: 0.6 });
      io.observe(el);
      return io;
    });
    return () => ios.forEach((io) => io?.disconnect());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <section id="how" className="border-t border-line bg-side">
      <div className="mx-auto max-w-6xl px-6 py-20">
        <Reveal><div className="font-mono text-xs text-muted">02 / WORKFLOW</div><h2 className="mt-2 font-display text-2xl font-semibold">How it works</h2></Reveal>
        <div className="mt-12 grid gap-12 lg:grid-cols-[1fr_1fr]">
          <div className="relative">
            <div ref={lineRef} className="grow-y absolute left-[11px] top-2 h-full w-px bg-line" />
            <ol className="space-y-14">
              {STEPS.map((s, i) => (
                <li key={s.n} ref={refs[i]} className="reveal-slow relative pl-10">
                  <span className={`absolute left-0 top-1 flex h-6 w-6 items-center justify-center rounded-full border bg-side font-mono text-[11px] transition-colors duration-300 ${active >= i ? "border-accent text-accent" : "border-line text-muted"}`}>{s.n}</span>
                  <h3 className="text-[18px] font-semibold">{s.title}</h3>
                  <p className="mt-2 max-w-md text-[15px] leading-relaxed text-fg2">{s.text}</p>
                </li>
              ))}
            </ol>
          </div>
          <div className="hidden lg:block">
            <div className="sticky top-24 rounded-md border border-line bg-surface p-6">
              <div className="mb-3 flex items-center justify-between font-mono text-[11px] text-muted"><span>STAGE {STEPS[active].n}</span><span>{STEPS[active].title.toUpperCase()}</span></div>
              <StepVisual step={active} />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default function Landing() {
  const { user } = useAuth();
  const enter = user ? "/overview" : "/login";
  return (
    <div className="min-h-screen bg-fog text-fg">
      <ScrollProgress />
      <header className="sticky top-0 z-20 border-b border-line bg-fog/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <Link to="/" className="font-display text-lg font-semibold tracking-tight">Doc<span className="text-accent">Sentry</span></Link>
          <nav className="hidden gap-7 text-sm text-fg2 md:flex">
            <a href="#features" className="transition-colors duration-150 hover:text-fg">Features</a>
            <a href="#how" className="transition-colors duration-150 hover:text-fg">How it works</a>
            <a href="#trust" className="transition-colors duration-150 hover:text-fg">Security and privacy</a>
          </nav>
          <div className="flex items-center gap-3">
            {!user && <Link to="/login" className="text-sm text-fg2 transition-colors duration-150 hover:text-fg">Sign in</Link>}
            <Link to={enter} className="btn-primary">Open workspace</Link>
          </div>
        </div>
      </header>

      {/* hero */}
      <section className="relative">
        <div className="mx-auto grid min-h-[calc(100vh-57px)] max-w-6xl items-center gap-12 px-6 pb-16 pt-12 lg:grid-cols-[1.05fr_0.95fr]">
          <div>
            <p className="hero-line eyebrow" style={{ animationDelay: "60ms" }}>Document forensics for lenders, auditors and compliance teams</p>
            <h1 className="mt-4 max-w-xl font-display text-[2.6rem] font-semibold leading-[1.08] tracking-tight md:text-[3.3rem]">
              <span className="hero-line block" style={{ animationDelay: "160ms" }}>Documents leave traces.</span>
              <span className="hero-line block" style={{ animationDelay: "280ms" }}>Find the evidence.</span>
            </h1>
            <p className="hero-line mt-5 max-w-lg text-[17px] leading-relaxed text-fg2" style={{ animationDelay: "400ms" }}>DocSentry helps investigators examine document structure, identify potential modifications, discover sensitive information exposure, and compare evidence across documents.</p>
            <div className="hero-line mt-8 flex flex-wrap gap-3" style={{ animationDelay: "500ms" }}>
              <Link to={enter} className="btn-primary h-10 px-5 text-[15px]">Explore the workspace</Link>
              <a href="#how" className="btn-secondary h-10 px-5 text-[15px]">See how it works</a>
            </div>
            <p className="hero-line mt-6 text-xs text-muted" style={{ animationDelay: "600ms" }}>Findings are indicators that need interpretation, not proof of fraud.</p>
          </div>
          <div className="hero-line" style={{ animationDelay: "350ms" }}><Evidence /></div>
        </div>
        <a href="#features" className="absolute bottom-5 left-1/2 hidden -translate-x-1/2 items-center gap-2 font-mono text-[11px] text-muted transition-colors hover:text-fg md:flex" aria-label="Scroll to features"><ArrowDown className="h-3.5 w-3.5" />scroll</a>
      </section>

      {/* features */}
      <section id="features" className="grid-fine border-t border-line">
        <div className="mx-auto max-w-6xl bg-fog/80 px-6 py-20">
          <Reveal><div className="font-mono text-xs text-muted">01 / ANALYSIS</div><h2 className="mt-2 font-display text-2xl font-semibold">What DocSentry does</h2><p className="mt-2 max-w-xl text-fg2">Seven capabilities, each implemented in the workspace and traceable to a page, a field and a rule.</p></Reveal>
          <div className="mt-12 space-y-2">
            {FEATURES.map((f, i) => (
              <div key={f.title}>
                <Rule />
                <Reveal slow className={`group grid gap-6 py-8 md:grid-cols-[6rem_1fr_1fr] ${i % 2 ? "md:[&>*:nth-child(2)]:order-3" : ""}`}>
                  <div className="font-mono text-xs text-muted"><div>{f.n}</div><div className="mt-1 text-accent">{f.tag}</div></div>
                  <div className="flex items-start gap-4"><f.icon className="mt-1 h-5 w-5 shrink-0 text-accent" /><div><h3 className="text-[18px] font-semibold">{f.title}</h3><p className="mt-2 max-w-md text-[15px] leading-relaxed text-fg2">{f.text}</p></div></div>
                  <div className="hidden items-center md:flex"><span className="border-l border-line pl-4 font-mono text-[11px] text-muted opacity-70 transition-opacity duration-200 group-hover:opacity-100">{f.note}</span></div>
                </Reveal>
              </div>
            ))}
            <Rule />
          </div>
        </div>
      </section>

      <HowItWorks />

      {/* trust */}
      <section id="trust" className="border-t border-line">
        <div className="mx-auto grid max-w-6xl gap-10 px-6 py-20 md:grid-cols-[1fr_1.4fr]">
          <Reveal><div className="font-mono text-xs text-muted">03 / LIMITS</div><h2 className="mt-2 font-display text-2xl font-semibold">Trust and limitations</h2><p className="mt-2 text-fg2">What the system claims, and what it does not.</p></Reveal>
          <Reveal slow>
            <ul className="divide-y divide-line border-y border-line text-[15px]">
              <li className="py-3"><span className="font-medium">Indicators, not verdicts.</span> <span className="text-fg2">Findings require interpretation by a reviewer; a match does not establish authenticity and a flag does not establish fraud.</span></li>
              <li className="py-3"><span className="font-medium">Masked identifiers.</span> <span className="text-fg2">Sensitive numbers found in a scan are displayed masked; the unmasked value is not stored.</span></li>
              <li className="py-3"><span className="font-medium">Access control.</span> <span className="text-fg2">Investigations are visible to their owner, reviewers and administrators under the application's authorization rules; every access is logged.</span></li>
              <li className="py-3"><span className="font-medium">Input-dependent results.</span> <span className="text-fg2">Quality depends on the document format, the extraction or OCR confidence and the checks that could run; each result states what was not checked and why.</span></li>
              <li className="py-3"><span className="font-medium">No external verification.</span> <span className="text-fg2">Checks are performed on the documents themselves; verification with issuing authorities is not performed.</span></li>
            </ul>
          </Reveal>
        </div>
      </section>

      {/* closing */}
      <section className="relative border-t border-line bg-gradient-to-b from-fog to-surface2">
        <div className="mx-auto grid max-w-6xl items-center gap-10 px-6 py-24 md:grid-cols-[1.3fr_0.7fr]">
          <Reveal slow>
            <h2 className="font-display text-[2rem] font-semibold leading-tight tracking-tight md:text-[2.6rem]">Start with the document.<br />Follow the evidence.</h2>
            <p className="mt-4 max-w-md text-fg2">Bring document analysis, investigation findings, and reporting into one workspace.</p>
            <Link to={enter} className="btn-primary mt-7 h-10 px-6 text-[15px]">Enter DocSentry</Link>
          </Reveal>
          <Reveal slow className="hidden justify-self-end md:block">
            <svg viewBox="0 0 160 200" className="h-[200px] w-[160px]" fill="none" aria-hidden>
              <path d="M24 10h78l34 34v142a6 6 0 0 1-6 6H24a6 6 0 0 1-6-6V16a6 6 0 0 1 6-6z" stroke="rgb(var(--line))" strokeWidth="1.5" />
              <path d="M102 10v28a6 6 0 0 0 6 6h28" stroke="rgb(var(--line))" strokeWidth="1.5" />
              {[70, 92, 114, 136].map((y, i) => <line key={y} x1="38" y1={y} x2={i === 2 ? 90 : 120} y2={y} stroke="rgb(var(--fg2))" strokeOpacity="0.5" strokeWidth="1.5" />)}
              <circle cx="128" cy="158" r="4" fill="rgb(var(--accent))" />
            </svg>
          </Reveal>
        </div>
      </section>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-6 text-sm text-muted">
          <span><span className="font-display font-semibold text-fg">DocSentry</span> {"\u00B7"} document intelligence, forensics and investigation workspace</span>
          <span className="font-mono text-xs">rule-based analysis {"\u00B7"} OCR for images {"\u00B7"} deterministic scoring</span>
        </div>
      </footer>
    </div>
  );
}