"""Normalisers for amounts, dates, months and names. Decimal everywhere, never float."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from rapidfuzz import fuzz

_CUR = re.compile(r"^(?:â‚¹|Rs\.?|INR)\s*", re.I)
_NUMERIC = re.compile(r"^(?:â‚¹|Rs\.?|INR)?\s*-?\(?\d+(?:,\d+)*(?:\.\d+)?\)?(?:\s*(?:Cr|Dr))?\.?$", re.I)
_DIR = re.compile(r"\s*(Cr|Dr)\.?$", re.I)
_FIND = re.compile(
    r"(?<![\w/.,-])(?:â‚¹|Rs\.?|INR)?\s*-?(?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d{1,2})?(?![\w/])")
DIRECTION_WORDS = {"cr", "dr", "cr.", "dr."}


@dataclass(frozen=True)
class Amount:
    value: Decimal
    direction: str | None = None  # "CR", "DR" or None


def is_numeric_word(s: str) -> bool:
    return bool(_NUMERIC.match(s.strip())) or s.strip().lower() in DIRECTION_WORDS


def is_amount_token(s: str) -> bool:
    s = s.strip()
    if not _NUMERIC.match(s):
        return False
    digits = re.sub(r"\D", "", s)
    return "." in s or "," in s or len(digits) >= 3


def parse_amount(s: str) -> Amount | None:
    raw = s.strip()
    if not raw:
        return None
    direction = None
    m = _DIR.search(raw)
    if m:
        direction = m.group(1).upper()
        raw = raw[: m.start()]
    raw = _CUR.sub("", raw.strip()).replace(" ", "")
    neg = False
    if raw.startswith("(") and raw.endswith(")"):
        neg, raw = True, raw[1:-1]
    if raw.startswith("-"):
        neg, raw = True, raw[1:]
    raw = raw.replace(",", "")
    if not re.fullmatch(r"\d+(?:\.\d{1,2})?", raw):
        return None
    try:
        val = Decimal(raw).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    return Amount(-val if neg else val, direction)


def find_amounts(text: str) -> list[Decimal]:
    out: list[Decimal] = []
    for m in _FIND.finditer(text):
        a = parse_amount(m.group(0))
        if a is not None and ("," in m.group(0) or "." in m.group(0) or len(m.group(0).strip()) >= 3):
            out.append(a.value)
    return out


def format_inr(d: Decimal) -> str:
    """Indian grouping: 1,25,000.00"""
    neg = d < 0
    s = f"{abs(d):.2f}"
    ip, fp = s.split(".")
    if len(ip) > 3:
        head, tail = ip[:-3], ip[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        ip = ",".join(groups) + "," + tail
    return ("-" if neg else "") + ip + "." + fp


# ---------------------------------------------------------------- dates
_ORD = re.compile(r"(\d{1,2})(st|nd|rd|th)", re.I)
_DATE_PATTERNS: list[tuple[re.Pattern[str], tuple[str, ...]]] = [
    (re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)"), ("%Y-%m-%d",)),
    (re.compile(r"(?<![\d/])(\d{1,2}[/.-]\d{1,2}[/.-]\d{4})(?![\d/])"), ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y")),
    (re.compile(r"(?<![\d/])(\d{1,2}[/-]\d{1,2}[/-]\d{2})(?![\d/])"), ("%d/%m/%y", "%d-%m-%y")),
    (re.compile(r"(?<!\w)(\d{1,2}(?:st|nd|rd|th)?[-/ ][A-Za-z]{3,9}\.?,?[-/ ]\d{4})(?!\d)"),
     ("%d-%b-%Y", "%d/%b/%Y", "%d %b %Y", "%d %B %Y", "%d-%B-%Y")),
    (re.compile(r"(?<!\w)(\d{1,2}[-/ ][A-Za-z]{3}[-/ ]\d{2})(?!\d)"), ("%d-%b-%y", "%d/%b/%y", "%d %b %y")),
    (re.compile(r"(?<!\w)([A-Za-z]{3,9}\.? \d{1,2},? \d{4})(?!\d)"), ("%B %d %Y", "%b %d %Y")),
]


def _try(s: str, fmts: tuple[str, ...]) -> date | None:
    s2 = _ORD.sub(r"\1", s).replace(",", "")
    s2 = re.sub(r"(?<=[A-Za-z])\.", "", s2)
    for f in fmts:
        try:
            return datetime.strptime(s2, f).date()
        except ValueError:
            continue
    return None


def parse_date(token: str) -> date | None:
    t = token.strip()
    for pat, fmts in _DATE_PATTERNS:
        m = pat.fullmatch(t)
        if m:
            return _try(m.group(1), fmts)
    return None


def find_dates(text: str) -> list[date]:
    hits: list[tuple[int, date]] = []
    for pat, fmts in _DATE_PATTERNS:
        for m in pat.finditer(text):
            d = _try(m.group(1), fmts)
            if d:
                hits.append((m.start(), d))
    hits.sort()
    return [d for _, d in hits]


def find_date(text: str) -> date | None:
    ds = find_dates(text)
    return ds[0] if ds else None


_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}
_MONTHS.update({k[:3]: v for k, v in _MONTHS.items()})


def parse_month(text: str) -> str | None:
    """Return YYYY-MM for strings like 'October 2026', 'Oct-26', '10/2026', '2026-10'."""
    t = text.strip().lower()
    m = re.search(r"([a-z]{3,9})\.?[\s,'/-]*(\d{4}|\d{2})\b", t)
    if m and m.group(1)[:3] in _MONTHS:
        y = int(m.group(2))
        y = y + 2000 if y < 100 else y
        return f"{y:04d}-{_MONTHS[m.group(1)[:3]]:02d}"
    m = re.search(r"\b(\d{1,2})[/-](\d{4})\b", t)
    if m and 1 <= int(m.group(1)) <= 12:
        return f"{int(m.group(2)):04d}-{int(m.group(1)):02d}"
    m = re.search(r"\b(\d{4})-(\d{2})\b", t)
    if m and 1 <= int(m.group(2)) <= 12:
        return f"{m.group(1)}-{m.group(2)}"
    d = find_date(text)
    return d.strftime("%Y-%m") if d else None


# ---------------------------------------------------------------- names
_HON = {"mr", "mrs", "ms", "miss", "dr", "shri", "smt", "sri", "kumari", "mx", "prof", "sh"}


def normalize_name(s: str) -> str:
    s = re.sub(r"[^A-Za-z ]+", " ", s).lower()
    return " ".join(t for t in s.split() if t not in _HON)


def name_similarity(a: str, b: str) -> float:
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return 0.0
    base = fuzz.token_set_ratio(na, nb) / 100
    ta, tb = na.split(), nb.split()

    def expand(ts: list[str], other: list[str]) -> list[str]:
        return [next((o for o in other if o.startswith(t)), t) if len(t) == 1 else t for t in ts]

    alt = fuzz.token_sort_ratio(" ".join(expand(ta, tb)), " ".join(expand(tb, ta))) / 100
    return max(base, alt)


def surnames_match(a: str, b: str) -> bool:
    ta, tb = normalize_name(a).split(), normalize_name(b).split()
    if not ta or not tb:
        return False
    return fuzz.ratio(ta[-1], tb[-1]) >= 85