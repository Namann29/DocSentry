"""Geometry-based table reconstruction from word coordinates.
Header keywords -> column spans; words are assigned to columns by type and position."""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..normalize import is_numeric_word, parse_date
from .base import Line, Word

NUMERIC_KEYS = {"debit", "credit", "balance", "amount", "qty", "rate", "hsn", "serial", "ref", "tax", "total"}
AMOUNT_KEYS = {"debit", "credit", "balance", "amount", "qty", "rate", "tax", "total"}


@dataclass
class Column:
    key: str
    x0: float
    x1: float

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2


def _clean(t: str) -> str:
    return re.sub(r"[^a-z0-9#]", "", t.lower())


def match_header(line: Line, spec: dict[str, list[str]], required: list[tuple[str, ...]]) -> list[Column] | None:
    toks = [_clean(w.text) for w in line.words]
    cands: list[tuple[str, list[str]]] = []
    for key, syns in spec.items():
        for syn in syns:
            parts = [p for p in (_clean(x) for x in syn.split()) if p]
            if parts:
                cands.append((key, parts))
    cands.sort(key=lambda kp: (-len(kp[1]), -sum(len(p) for p in kp[1])))
    used: set[int] = set()
    cols: list[Column] = []
    done: set[str] = set()
    for key, parts in cands:
        if key in done:
            continue
        joined, n = "".join(parts), len(parts)
        hit = None
        for i in range(len(toks)):
            if i in used:
                continue
            if toks[i] == joined:
                hit = (i, i + 1)
                break
            if n > 1 and i + n <= len(toks) and toks[i:i + n] == parts and not any(j in used for j in range(i, i + n)):
                hit = (i, i + n)
                break
        if hit:
            a, b = hit
            used.update(range(a, b))
            ws = line.words[a:b]
            cols.append(Column(key, ws[0].x0, ws[-1].x1))
            done.add(key)
    keys = {c.key for c in cols}
    if not all(any(k in keys for k in group) for group in required):
        return None
    if len(used) < max(2, 0.6 * len(toks)):
        return None
    return sorted(cols, key=lambda c: c.x0)


def find_table(lines: list[Line], spec: dict[str, list[str]],
               required: list[tuple[str, ...]]) -> tuple[int, list[Column]] | None:
    for i, line in enumerate(lines):
        cols = match_header(line, spec, required)
        if cols:
            return i, cols
    return None


def assign(line: Line, cols: list[Column]) -> dict[str, list[Word]]:
    """Dates -> date column; numeric-looking words -> nearest column centre;
    other text -> the right-most non-amount column that starts at or before the word."""
    cells: dict[str, list[Word]] = {c.key: [] for c in cols}
    numeric = [c for c in cols if c.key in NUMERIC_KEYS]
    textc = [c for c in cols if c.key not in AMOUNT_KEYS]
    datec = next((c for c in cols if c.key == "date"), None)
    for w in line.words:
        if datec and parse_date(w.text):
            target = datec
        elif numeric and is_numeric_word(w.text):
            target = min(cols, key=lambda c: abs(c.cx - w.cx))
        elif textc:
            left = [c for c in textc if c.x0 <= w.x0 + 3]
            target = max(left, key=lambda c: c.x0) if left else min(textc, key=lambda c: abs(c.cx - w.cx))
        else:
            target = min(cols, key=lambda c: abs(c.cx - w.cx))
        cells[target.key].append(w)
    return cells


def cell_text(cells: dict[str, list[Word]], key: str) -> str:
    return " ".join(w.text for w in cells.get(key, []))