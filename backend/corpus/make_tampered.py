"""Produce a modified copy of a generated salary slip: the net pay is replaced in a different font and the
file is saved incrementally, leaving the traces the security scan looks for. Demo and test helper."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.extraction.service import run_extraction  # noqa: E402


def tamper_net_pay(src: Path, dst: Path, new_value: str = "75,000.00") -> dict:
    shutil.copyfile(src, dst)
    out = run_extraction(src)
    fld = next((f for f in (out.result.fields if out.result else []) if f.name == "net_pay" and f.bbox), None)
    if fld is None:
        raise SystemExit("net_pay field with a bounding box not found in the source slip")
    x0, y0, x1, y1 = fld.bbox
    words = out.pages[fld.page - 1].words
    amount_words = [w for w in words if w.text.replace(",", "") == fld.value.replace(",", "") and w.x0 >= x0 - 1 and w.x1 <= x1 + 1]
    if amount_words:  # replace only the amount, not its label
        w = amount_words[-1]
        x0, y0, x1, y1 = w.x0, w.y0, w.x1, w.y1
    with fitz.open(str(dst)) as doc:
        page = doc[fld.page - 1]
        page.add_redact_annot(fitz.Rect(x0 - 1, y0 - 1, x1 + 1, y1 + 1), fill=(1, 1, 1))
        page.apply_redactions()
        page.insert_text((x0, y1 - 2), new_value, fontname="cour", fontsize=9)
        doc.save(str(dst), incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
    return {"page": fld.page, "bbox": fld.bbox, "original": fld.value, "replaced_with": new_value}


if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "out" / "scenario_1_consistent" / "salary_slip.pdf"
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_name("salary_slip_modified.pdf")
    print(tamper_net_pay(src, dst), "->", dst)