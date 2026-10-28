from __future__ import annotations

import re
from decimal import Decimal

from ..extraction.base import Line, PageText
from ..identifiers import PAN_MASKED_RE
from ..normalize import is_amount_token, parse_amount, parse_month
from .base import DocumentParser, ParseResult, all_lines, letterhead, register, scan_labels

META = {
    "employee_name": ["employee name", "name of employee", "emp name", "emp. name", "name"],
    "employee_code": ["employee code", "employee id", "emp code", "emp id", "employee no", "emp. code", "emp. id", "employee number"],
    "designation": ["designation", "position", "job title"],
    "department": ["department", "dept"],
    "pan": ["pan no", "pan number", "pan"],
    "bank_account": ["bank a/c no", "bank account no", "bank account", "account no", "a/c no", "bank a/c", "account number"],
    "uan": ["uan no", "uan"],
    "month": ["salary slip for the month of", "payslip for the month of", "pay slip for the month of",
              "for the month of", "pay period", "salary month", "pay month", "salary for", "month", "period"],
    "paid_days": ["paid days", "days paid", "working days", "payable days"],
    "date_of_joining": ["date of joining", "doj", "joining date"],
    "location": ["location", "work location"],
}
NET = ("net pay", "net salary", "net amount", "take home", "net payable", "net earnings", "net")
GROSS = ("gross earnings", "gross salary", "gross pay", "total earnings", "gross", "total earning")
TOTAL_DED = ("total deductions", "total deduction")
DED_WORDS = ("provident", "pf", "epf", "esi", "esic", "tax", "tds", "professional", "loan", "advance",
             "insurance", "deduction", "recovery", "lwp", "lop", "nps", "lic")
CURRENCY = {"rs", "rs.", "â‚¹", "inr", "(rs)", "(rs.)", "(inr)"}


def _segments(line: Line) -> list[tuple[str, str, list]]:
    out, buf = [], []
    for w in line.words:
        t = w.text
        if t.lower() in CURRENCY:
            continue
        if is_amount_token(t):
            out.append((" ".join(x.text for x in buf).strip(" :-"), t, buf + [w]))
            buf = []
        else:
            buf.append(w)
    return out


@register
class SalarySlipParser(DocumentParser):
    doc_type = "salary_slip"

    def parse(self, pages: list[PageText]) -> ParseResult:
        res = ParseResult(self.doc_type)
        lines = all_lines(pages)
        employer, line = letterhead(lines)
        res.add("employer", employer, line=line, confidence=0.7)
        res.data["employer"] = employer
        meta = scan_labels(lines, META)
        for key in ("employee_name", "employee_code", "designation", "department", "bank_account", "uan",
                    "paid_days", "date_of_joining", "location"):
            if key in meta and meta[key][0]:
                val = meta[key][0]
                res.add(key, val, line=meta[key][1])
                res.data[key] = val
        if "pan" in meta:
            m = PAN_MASKED_RE.search(meta["pan"][0].upper())
            if m:
                res.data["pan"] = m.group(1)
                res.add("pan", m.group(1), line=meta["pan"][1])
        if "month" in meta:
            mo = parse_month(meta["month"][0])
            if mo:
                res.data["month"] = mo
                res.add("month", meta["month"][0], mo, line=meta["month"][1])
        if "month" not in res.data:
            for ln in lines[:12]:
                if re.search(r"month|period|payslip|salary slip", ln.text, re.I):
                    mo = parse_month(ln.text)
                    if mo:
                        res.data["month"] = mo
                        res.add("month", ln.text, mo, line=ln, confidence=0.8)
                        break

        split_x = None
        section = "earnings"
        earnings: dict[str, str] = {}
        deductions: dict[str, str] = {}
        for ln in lines:
            low = ln.text.lower().strip()
            ded_w = next((w for w in ln.words if w.text.lower().startswith("deduction")), None)
            if ded_w and any(w.text.lower().startswith("earning") for w in ln.words):
                split_x = ded_w.x0 - 2
                continue
            if low in ("deductions", "deduction", "earnings", "earning"):
                section = "deductions" if low.startswith("ded") else "earnings"
                continue
            for label, amt_txt, ws in _segments(ln):
                a = parse_amount(amt_txt)
                if a is None:
                    continue
                lab = re.sub(r"\s+", " ", label).strip().lower()
                lab_clean = re.sub(r"[^a-z &/().-]", "", lab).strip()
                if any(k in lab for k in TOTAL_DED):
                    res.data["total_deductions"] = str(a.value)
                    res.add("total_deductions", amt_txt, str(a.value), words=ws)
                elif any(lab.startswith(k) or lab.endswith(k) for k in NET):
                    res.data["net_pay"] = str(a.value)
                    res.add("net_pay", amt_txt, str(a.value), words=ws)
                elif any(k in lab for k in GROSS):
                    res.data["gross"] = str(a.value)
                    res.add("gross", amt_txt, str(a.value), words=ws)
                elif not lab_clean or re.search(r"period|month|date|code|days|year|uan|a/c|account|pan|no\b", lab):
                    continue
                elif "." not in amt_txt and "," not in amt_txt and not any(k in lab for k in DED_WORDS):
                    continue
                else:
                    is_ded = (split_x is not None and ws[-1].cx > split_x) or section == "deductions" \
                        or any(re.search(rf"\b{k}\b", lab) for k in DED_WORDS)
                    target = deductions if is_ded else earnings
                    target[lab_clean] = str(a.value)
                    res.add(f"{'deduction' if is_ded else 'earning'}[{lab_clean}]", amt_txt, str(a.value), words=ws)
        res.data["earnings"], res.data["deductions"] = earnings, deductions
        if earnings:
            res.data["earnings_total"] = str(sum((Decimal(v) for v in earnings.values()), Decimal(0)))
        if deductions:
            res.data["deductions_total"] = str(sum((Decimal(v) for v in deductions.values()), Decimal(0)))
        if "net_pay" not in res.data:
            res.warnings.append("Net pay not found")
        return res