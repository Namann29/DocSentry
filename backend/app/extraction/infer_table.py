"""Header-independent transaction-table inference.
Columns come from where amount tokens line up; every row needs a date; the right-most column must behave like a
running balance. Debit/credit direction is the assignment that makes the arithmetic reconcile. The result is
accepted only if most rows reconcile, so unseen bank layouts parse without any header vocabulary and a wrong
inference is rejected rather than reported."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from ..normalize import is_amount_token, parse_amount, parse_date
from .base import PageText, Word

TOL = 14.0           # points: tolerance for right-edge alignment of amounts
RECONCILE_MIN = 0.6  # share of rows that must reconcile for the inference to be accepted
STOP = ("closing balance", "statement summary", "end of statement", "total debit", "total credit")


def _is_amount(w: Word) -> bool:
    return is_amount_token(w.text) and ("." in w.text or "," in w.text) and parse_date(w.text) is None


def _clusters(xs: list[float], tol: float) -> list[list[float]]:
    out: list[list[float]] = []
    for x in sorted(xs):
        if out and x - out[-1][-1] <= tol:
            out[-1].append(x)
        else:
            out.append([x])
    return out


def _row(r: dict[str, Any], dr: Decimal | None, cr: Decimal | None, inferred: bool) -> dict[str, Any]:
    return {"serial": r["serial"], "date": r["date"], "description": r["description"], "ref": None,
            "debit": str(dr) if dr is not None else None, "credit": str(cr) if cr is not None else None,
            "balance": str(r["balance"]), "direction_inferred": inferred, "page": r["page"], "bbox": r["bbox"],
            "confidence": 0.8, "_line": r["line"], "_cells": r["cells"]}


def _reconcile(rows: list[dict[str, Any]], opening: Decimal | None, swap: bool) -> float:
    prev, ok, total = opening, 0, 0
    for r in rows:
        dr, cr = (r["col_b"], r["col_a"]) if swap else (r["col_a"], r["col_b"])
        if prev is not None:
            total += 1
            if abs(prev + (cr or Decimal(0)) - (dr or Decimal(0)) - r["balance"]) <= Decimal("0.02"):
                ok += 1
        prev = r["balance"]
    return ok / total if total else 0.0


def infer_transactions(pages: list[PageText], opening: Decimal | None = None) -> tuple[list[dict[str, Any]], list[str], Decimal | None]:
    cands = []
    for p in pages:
        for idx, ln in enumerate(p.lines):
            dates = [w for w in ln.words if parse_date(w.text)]
            amts = [w for w in ln.words if _is_amount(w)]
            if dates and amts:
                cands.append((p, idx, ln, dates[0], amts))
    if len(cands) < 3:
        return [], [], opening
    clusters = [c for c in _clusters([w.x1 for *_, a in cands for w in a], TOL) if len(c) >= 2]  # a column exists once two amounts align; credits are rare on most statements
    if not clusters:
        return [], ["Amount columns could not be inferred from the layout"], opening
    cols = sorted((min(c) - TOL, max(c) + TOL) for c in clusters)
    ncol = len(cols)

    def col_of(w: Word) -> int | None:
        for i, (lo, hi) in enumerate(cols):
            if lo <= w.x1 <= hi:
                return i
        return None

    rows: list[dict[str, Any]] = []
    for p, idx, ln, date, amts in cands:
        cells: dict[int, Word] = {}
        for w in amts:
            i = col_of(w)
            if i is not None and i not in cells:
                cells[i] = w
        if ncol - 1 not in cells:
            continue
        bal = parse_amount(cells[ncol - 1].text)
        if bal is None:
            continue
        taken = set(id(w) for w in cells.values())
        first_amt_x0 = min(w.x0 for w in cells.values())
        desc = " ".join(w.text for w in ln.words if id(w) not in taken and w is not date and date.x1 <= w.x0 < first_amt_x0)
        serial = " ".join(w.text for w in ln.words if w.x1 <= date.x0 and w.text.isdigit()) or None
        if "opening" in desc.lower() and len(cells) == 1:
            opening = bal.value
            continue
        a = parse_amount(cells[ncol - 3].text) if ncol >= 3 and (ncol - 3) in cells else None
        b = parse_amount(cells[ncol - 2].text) if ncol >= 2 and (ncol - 2) in cells else None
        rows.append({"page": p.number, "line": idx, "date": parse_date(date.text).isoformat(), "description": desc, "serial": serial,
                     "balance": bal.value, "bbox": ln.bbox, "col_a": a.value if a else None, "col_b": b.value if b else None,
                     "dir": b.direction if b else None,
                     "cells": {"date": [date.x0, date.y0, date.x1, date.y1], **{k: [w.x0, w.y0, w.x1, w.y1] for k, w in (("balance", cells[ncol - 1]),)},
                               **({"a": [cells[ncol - 3].x0, cells[ncol - 3].y0, cells[ncol - 3].x1, cells[ncol - 3].y1]} if ncol >= 3 and (ncol - 3) in cells else {}),
                               **({"b": [cells[ncol - 2].x0, cells[ncol - 2].y0, cells[ncol - 2].x1, cells[ncol - 2].y1]} if ncol >= 2 and (ncol - 2) in cells else {})}})
    if len(rows) < 3:
        return [], ["Too few transaction-like rows to infer a table"], opening

    txns: list[dict[str, Any]] = []
    if ncol >= 3:  # three or more amount columns: [.., debit, credit, balance] or swapped; arithmetic decides
        r1, r2 = _reconcile(rows, opening, False), _reconcile(rows, opening, True)
        swap, rate = r2 > r1, max(r1, r2)
        if rate < RECONCILE_MIN:
            return [], [f"Inferred table rejected: only {rate:.0%} of rows reconcile with the balance column"], opening
        for r in rows:
            dr, cr = (r["col_b"], r["col_a"]) if swap else (r["col_a"], r["col_b"])
            txns.append(_row(r, dr, cr, False))
    else:  # single amount column: sign, Cr/Dr marker, or balance delta
        prev, ok, total, tmp = opening, 0, 0, []
        for r in rows:
            v = r["col_b"]
            dr = cr = None
            inferred = False
            if v is not None:
                if r["dir"] == "DR" or v < 0:
                    dr = abs(v)
                elif r["dir"] == "CR":
                    cr = v
                elif prev is not None:
                    delta = r["balance"] - prev
                    if abs(delta - v) <= Decimal("0.02"):
                        cr, inferred = v, True
                    elif abs(delta + v) <= Decimal("0.02"):
                        dr, inferred = v, True
                    else:
                        cr, inferred = v, True
                else:
                    cr, inferred = v, True
            if prev is not None:
                total += 1
                if abs(prev + (cr or Decimal(0)) - (dr or Decimal(0)) - r["balance"]) <= Decimal("0.02"):
                    ok += 1
            prev = r["balance"]
            tmp.append((r, dr, cr, inferred))
        rate = ok / total if total else 0.0
        if rate < RECONCILE_MIN:
            return [], [f"Inferred table rejected: only {rate:.0%} of rows reconcile with the balance column"], opening
        txns = [_row(r, dr, cr, inf) for r, dr, cr, inf in tmp]

    # multi-line descriptions: text-only lines directly after a row, before the next row or a footer
    by_line = {(t["page"], t["_line"]): t for t in txns}
    for p in pages:
        current = None
        for idx, ln in enumerate(p.lines):
            key = (p.number, idx)
            if key in by_line:
                current = by_line[key]
                continue
            low = ln.text.lower()
            if any(s in low for s in STOP):
                current = None
                continue
            if current and ln.words and not any(parse_date(w.text) or _is_amount(w) for w in ln.words) and all(w.x0 >= 50 for w in ln.words):
                current["description"] = (current["description"] + " " + ln.text).strip()
            else:
                current = None
    for i, t in enumerate(txns):
        t["index"] = i
        t.pop("_line", None)
    return txns, [], opening