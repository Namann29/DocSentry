import { useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useDocument, usePageImage, useSecurity } from "../../api/hooks";
import { DOC_TYPE_LABEL } from "../../api/types";
import { Badge, ErrorBox, Skeleton } from "../../components/ui";

const ZOOM = 1.5; // the backend renders pages at 1.5x PDF points

export default function DocumentViewer() {
  const docId = Number(useParams().docId);
  const [params] = useSearchParams();
  const doc = useDocument(docId);
  const sec = useSecurity(docId);
  const [page, setPage] = useState(Number(params.get("page") || 1));
  const [selected, setSelected] = useState<string | null>(params.get("field") ? `f:${params.get("field")}` : params.get("hl") ? `m:${params.get("hl")}` : null);
  const [showMods, setShowMods] = useState(params.get("mods") !== "0");
  const [showFields, setShowFields] = useState(true);
  const [zoom, setZoom] = useState(1);
  const [scale, setScale] = useState(1);
  const img = usePageImage(docId, page);
  const imgRef = useRef<HTMLImageElement>(null);
  if (doc.isLoading) return <Skeleton rows={8} />;
  if (doc.error || !doc.data) return <ErrorBox error={doc.error ?? "Not found"} />;
  const d = doc.data;
  const fields = d.fields.filter((f) => f.page === page && f.bbox);
  const mods = (sec.data?.modification_indicators ?? []).map((m, i) => ({ ...m, idx: i })).filter((m) => m.page === page);
  const allMods = sec.data?.modification_indicators ?? [];
  const box = (b: number[]) => ({ left: b[0] * ZOOM * scale * zoom - 2, top: b[1] * ZOOM * scale * zoom - 2, width: (b[2] - b[0]) * ZOOM * scale * zoom + 4, height: (b[3] - b[1]) * ZOOM * scale * zoom + 4 });
  return (
    <div className="grid gap-4 lg:grid-cols-[150px_1fr_300px]">
      <aside className="card p-3">
        <div className="eyebrow mb-2">Pages</div>
        <ul className="space-y-1">
          {Array.from({ length: d.page_count }, (_, i) => i + 1).map((p) => (
            <li key={p}><button onClick={() => setPage(p)} className={`flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm ${p === page ? "bg-accent-50 font-medium text-accent-700 dark:bg-ink-700" : "hover:bg-fog dark:hover:bg-ink-700"}`}>
              <span>Page {p}</span>{allMods.some((m) => m.page === p) && <span className="h-2 w-2 rounded-full bg-amber-500" title="modification indicator" />}
            </button></li>
          ))}
        </ul>
      </aside>
      <section className="card min-w-0 overflow-hidden">
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-2 dark:border-ink-700">
          <div className="min-w-0"><div className="truncate text-sm font-semibold">{d.original_filename}</div><div className="text-xs text-slate-500">{DOC_TYPE_LABEL[d.doc_type] ?? d.doc_type}, {d.extraction_method}</div></div>
          <div className="flex items-center gap-1">
            <button className="btn-secondary px-2" onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))} aria-label="Zoom out">âˆ’</button>
            <span className="w-12 text-center text-xs tabular-nums">{Math.round(zoom * 100)}%</span>
            <button className="btn-secondary px-2" onClick={() => setZoom((z) => Math.min(3, z + 0.25))} aria-label="Zoom in">+</button>
            <button className="btn-secondary" onClick={() => setZoom(1)}>Fit</button>
          </div>
        </header>
        <div className="workspace overflow-auto rounded-b-xl rounded-t-none p-6" style={{ maxHeight: "78vh" }}>
          {img.isLoading ? <Skeleton rows={12} /> : img.error ? <ErrorBox error={img.error} /> : (
            <div className="relative inline-block" style={{ width: `${zoom * 100}%` }}>
              <img ref={imgRef} src={img.data} alt={`page ${page}`} className="w-full bg-paper shadow-page" onLoad={() => imgRef.current && setScale(imgRef.current.clientWidth / imgRef.current.naturalWidth / zoom)} />
              {showFields && fields.map((f) => <div key={f.id} title={`${f.name}: ${f.value}`} onClick={() => setSelected(`f:${f.name}`)}
                className={`absolute cursor-pointer border ${selected === `f:${f.name}` ? "border-accent-600 bg-accent-500/25" : f.corrected ? "border-emerald-500 bg-emerald-400/10" : "border-accent-400/70 bg-accent-400/10"}`} style={box(f.bbox!)} />)}
              {showMods && mods.map((m) => <div key={m.idx} title={`${m.text}: ${m.font} differs from ${m.dominant_font}`} onClick={() => setSelected(`m:${m.idx}`)}
                className={`absolute animate-pop cursor-pointer border-2 ${selected === `m:${m.idx}` ? "border-amber-600 bg-amber-400/40" : "border-amber-500 bg-amber-400/20"}`} style={box(m.bbox)} />)}
            </div>
          )}
        </div>
      </section>
      <aside className="space-y-4">
        <div className="card p-3 text-sm">
          <div className="eyebrow mb-2">Overlays</div>
          <label className="flex items-center gap-2"><input type="checkbox" checked={showMods} onChange={(e) => setShowMods(e.target.checked)} /><span className="inline-block h-3 w-3 border-2 border-amber-500 bg-amber-400/30" />Potential modifications ({allMods.length})</label>
          <label className="mt-1 flex items-center gap-2"><input type="checkbox" checked={showFields} onChange={(e) => setShowFields(e.target.checked)} /><span className="inline-block h-3 w-3 border border-accent-400 bg-accent-400/20" />Extracted fields ({d.fields.length})</label>
          <p className="mt-2 text-xs text-slate-500">Amber: a numeric value set in a font family different from the page's dominant font. A potential modification, not proof of one.</p>
        </div>
        {allMods.length > 0 && (
          <div className="card p-3">
            <div className="eyebrow mb-2">Modification indicators</div>
            <ul className="space-y-1">{allMods.map((m, i) => <li key={i}><button onClick={() => { setPage(m.page); setSelected(`m:${i}`); }} className={`w-full rounded px-2 py-1 text-left text-sm hover:bg-fog dark:hover:bg-ink-700 ${selected === `m:${i}` ? "bg-amber-50 dark:bg-ink-700" : ""}`}><span className="amount font-medium">{m.text}</span><span className="block text-xs text-slate-500">p.{m.page}, {m.font}</span></button></li>)}</ul>
          </div>
        )}
        <div className="card p-3">
          <div className="eyebrow mb-2">Fields on this page</div>
          {fields.length === 0 ? <div className="text-sm text-slate-500">No positioned fields on this page.</div> : (
            <ul className="max-h-[40vh] space-y-1 overflow-auto">{fields.map((f) => <li key={f.id}><button onClick={() => setSelected(`f:${f.name}`)} className={`w-full rounded px-2 py-1 text-left text-sm hover:bg-fog dark:hover:bg-ink-700 ${selected === `f:${f.name}` ? "bg-accent-50 dark:bg-ink-700" : ""}`}>
              <span className="flex justify-between"><span className="mono text-slate-500">{f.name}</span><Badge tone={f.confidence >= 0.9 ? "ok" : f.confidence >= 0.7 ? "medium" : "high"}>{f.confidence.toFixed(2)}</Badge></span><span className="block truncate">{f.value}</span></button></li>)}</ul>
          )}
          <Link className="link mt-2 block text-xs" to={`../review/${d.id}`}>Open extraction review</Link>
        </div>
      </aside>
    </div>
  );
}