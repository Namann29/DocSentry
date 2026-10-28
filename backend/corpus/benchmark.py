"""Extraction benchmark: transaction-level precision/recall/F1 per statement template,
reported separately for development templates (1-3) and HELD-OUT templates (4-5)."""
from __future__ import annotations

import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.extraction.service import run_extraction  # noqa: E402
from corpus.generate import build_scenario, render_scenario  # noqa: E402


def row_key(date: str, debit: str | None, credit: str | None, balance: str | None) -> tuple:
    q = lambda v: str(Decimal(v).quantize(Decimal("0.01"))) if v else None  # noqa: E731
    return (date, q(debit), q(credit), q(balance))


def main() -> None:
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        for sid in range(1, 6):
            scn = build_scenario(sid)
            files = render_scenario(scn, Path(tmp) / str(sid))
            t0 = time.perf_counter()
            out = run_extraction(files["bank_statement"])
            secs = time.perf_counter() - t0
            truth = {row_key(t.date.isoformat(), str(t.debit) if t.debit else None, str(t.credit) if t.credit else None, str(t.balance)) for t in scn.account.txns}
            got = {row_key(r["date"], r["debit"], r["credit"], r["balance"]) for r in (out.result.data["transactions"] if out.result else [])}
            tp = len(truth & got)
            p = tp / len(got) if got else 0.0
            r = tp / len(truth) if truth else 0.0
            f1 = 2 * p * r / (p + r) if p + r else 0.0
            results.append((sid, scn.account.template, out.classification.doc_type, len(truth), len(got), p, r, f1, secs / max(1, len(out.pages))))
    print(f"{'scn':>3} {'tmpl':>4} {'set':>8} {'classified':>16} {'truth':>5} {'got':>4} {'P':>6} {'R':>6} {'F1':>6} {'s/page':>7}")
    for sid, tm, cls, nt, ng, p, r, f1, spp in results:
        print(f"{sid:>3} {tm:>4} {'held-out' if tm >= 4 else 'dev':>8} {cls:>16} {nt:>5} {ng:>4} {p:6.3f} {r:6.3f} {f1:6.3f} {spp:7.3f}")
    dev = [x[7] for x in results if x[1] <= 3]
    held = [x[7] for x in results if x[1] >= 4]
    print(f"\nmean F1 dev templates: {sum(dev)/len(dev):.3f}   held-out templates: {sum(held)/len(held):.3f}   gap: {sum(dev)/len(dev)-sum(held)/len(held):+.3f}")
    print("Note: scenario 4 deliberately corrupts one balance, so its truth row 14 is not expected to match.")


if __name__ == "__main__":
    main()