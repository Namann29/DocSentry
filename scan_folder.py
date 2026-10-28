"""Local batch check: run the extraction ladder and the security scan over every PDF/PNG/JPG in a folder.
Nothing is uploaded or stored; results are printed only. Use it to see how DocSentry behaves on your own files."""
from __future__ import annotations

import sys
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.extraction.service import run_extraction  # noqa: E402
from app.security_scan import scan_document  # noqa: E402
from app.upload import inspect_pdf  # noqa: E402


def main(folder: Path) -> None:
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in (".pdf", ".png", ".jpg", ".jpeg"))
    print(f"{'file':40} {'type':18} {'conf':>5} {'via':14} {'score':>5} {'level':22} {'mods':>4} {'ids':>4} notes")
    for f in files:
        try:
            data = f.read_bytes()
            flags, meta, ctype = [], {}, "application/pdf" if f.suffix.lower() == ".pdf" else "image/png"
            if ctype == "application/pdf":
                insp = inspect_pdf(data)
                flags, meta = insp.flags, insp.metadata
            out = run_extraction(f)
            s = scan_document(f, out.pages, flags, meta, "", len(data), ctype)
            weak = out.classification.scores.get("_weak_parse")
            notes = "; ".join((out.result.warnings if out.result else [])[:2])
            print(f"{f.name[:40]:40} {out.classification.doc_type:18} {out.classification.confidence:5.2f} {out.method:14} {s['score']:5} {s['level']:22} "
                  f"{len(s['modification_indicators']):4} {len(s['sensitive']):4} {'weak; ' if weak else ''}{notes[:60]}")
        except Exception as e:  # noqa: BLE001
            print(f"{f.name[:40]:40} ERROR {type(e).__name__}: {e}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Downloads")