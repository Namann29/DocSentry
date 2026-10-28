from __future__ import annotations

import re
from decimal import Decimal

from ..extraction.base import PageText
from ..extraction.tables import assign, cell_text, find_table
from ..identifiers import GSTIN_RE
from ..normalize import find_amounts, find_date, parse_amount
from .base import DocumentParser, ParseResult, all_lines, full_text, letterhead, register, scan_labels
from .invoice import ITEM_HEADER, ITEM_REQUIRED, ITEM_STOP

_NAME = r"((?:[A-Z][A-Za-z.'-]+\s+){0,3}[A-Z][A-Za-z.'-]+)"
_HON = r"(?:Mr\.?|Ms\.?|Mrs\.?|Shri|Smt\.?|Dr\.?)?\s*"


@register
class EmploymentLetterParser(DocumentParser):
    doc_type = "employment_letter"

    def parse(self, pages: list[PageText]) -> ParseResult:
        res = ParseResult(self.doc_type)
        lines = all_lines(pages)
        text = full_text(pages)
        employer, el = letterhead(lines)
        res.add("employer", employer, line=el, confidence=0.7)
        res.data["employer"] = employer
        for ln in lines[:10]:
            d = find_date(ln.text)
            if d:
                res.data["letter_date"] = d.isoformat()
                res.add("letter_date", ln.text, d.isoformat(), line=ln)
                break
        m = re.search(r"(?:certify that|confirm that|state that|Dear)\s+" + _HON + _NAME, text)
        if m:
            res.data["employee_name"] = m.group(1).rstrip(",.")
            res.add("employee_name", res.data["employee_name"], confidence=0.85)
        m = re.search(r"\(?Employee (?:Code|ID|No\.?)[:\s]*([A-Z0-9-]+)\)?", text, re.I)
        if m:
            res.data["employee_code"] = m.group(1)
            res.add("employee_code", m.group(1))
        m = re.search(r"(?:designation of|designated as|as an?|position of|role of|working as an?)\s+([A-Z][A-Za-z ]+?)(?=\s+(?:with|at|in|since|from|and|w\.e\.f)\b|[.,])", text)
        if m:
            res.data["designation"] = m.group(1).strip()
            res.add("designation", res.data["designation"], confidence=0.85)
        m = re.search(r"(?:employed with|working with|employee of|employed at|working at)\s+((?:[A-Z][A-Za-z&.]*\s*){1,6}?)(?=\s+(?:as|since|from|in)\b|[.,])", text)
        if m:
            res.data["employer_stated"] = m.group(1).strip()
            res.add("employer_stated", res.data["employer_stated"], confidence=0.8)
        for key, pat in (("gross_monthly_salary", r"gross (?:monthly )?salary[^0-9]{0,40}?((?:Rs\.?|INR|â‚¹)?\s*[\d,]+(?:\.\d{2})?)"),
                         ("net_monthly_salary", r"net (?:monthly )?(?:salary|pay|take[- ]home)[^0-9]{0,40}?((?:Rs\.?|INR|â‚¹)?\s*[\d,]+(?:\.\d{2})?)"),
                         ("annual_ctc", r"(?:CTC|cost to company|per annum)[^0-9]{0,40}?((?:Rs\.?|INR|â‚¹)?\s*[\d,]+(?:\.\d{2})?)"),
                         ("monthly_salary", r"monthly (?:salary|remuneration)[^0-9]{0,40}?((?:Rs\.?|INR|â‚¹)?\s*[\d,]+(?:\.\d{2})?)")):
            m = re.search(pat, text, re.I)
            if m:
                a = parse_amount(m.group(1))
                if a:
                    res.data[key] = str(a.value)
                    res.add(key, m.group(1), str(a.value), confidence=0.85)
        m = re.search(r"(?:since|joined (?:us |the company )?on|with effect from|w\.e\.f\.?)\s+([^.;,]{4,30})", text, re.I)
        if m:
            d = find_date(m.group(1))
            if d:
                res.data["joining_date"] = d.isoformat()
                res.add("joining_date", m.group(1).strip(), d.isoformat(), confidence=0.85)
        if "employee_name" not in res.data:
            res.warnings.append("Employee name not found")
        return res


PO_META = {
    "po_number": ["po no.", "po no", "po number", "purchase order no.", "purchase order no", "purchase order number", "order no"],
    "po_date": ["po date", "order date", "date"],
    "vendor": ["vendor", "supplier", "to"],
    "buyer": ["buyer", "issued by", "bill to"],
    "delivery_date": ["delivery date", "expected delivery"],
}
PO_TOTALS = {"total": ["order total", "grand total", "total value", "order value", "total"]}


@register
class PurchaseOrderParser(DocumentParser):
    doc_type = "purchase_order"

    def parse(self, pages: list[PageText]) -> ParseResult:
        res = ParseResult(self.doc_type)
        lines = all_lines(pages)
        buyer, bl = letterhead([ln for ln in lines if not re.fullmatch(r"\s*purchase order\s*", ln.text, re.I)])
        res.add("buyer", buyer, line=bl, confidence=0.7)
        res.data["buyer"] = buyer
        meta = scan_labels(lines, PO_META)
        for key in ("po_number", "vendor", "delivery_date"):
            if key in meta and meta[key][0]:
                val = re.split(r"\s{2,}|\s+gstin", meta[key][0], flags=re.I)[0].strip()
                res.data[key] = val
                res.add(key, val, line=meta[key][1])
        if "po_date" in meta:
            d = find_date(meta["po_date"][0])
            if d:
                res.data["po_date"] = d.isoformat()
                res.add("po_date", meta["po_date"][0], d.isoformat(), line=meta["po_date"][1])
        gstins = [m.group(1) for m in GSTIN_RE.finditer(full_text(pages))]
        if gstins:
            res.data["buyer_gstin"] = gstins[0]
        if len(gstins) > 1:
            res.data["vendor_gstin"] = gstins[1]
        items: list[dict] = []
        for page in pages:
            found = find_table(page.lines, ITEM_HEADER, ITEM_REQUIRED)
            if not found:
                continue
            idx, cols = found
            for line in page.lines[idx + 1:]:
                if any(s in line.text.lower() for s in ITEM_STOP):
                    break
                cells = assign(line, cols)
                amt = parse_amount(cell_text(cells, "amount"))
                if amt is None:
                    continue
                qty, rate = parse_amount(cell_text(cells, "qty")), parse_amount(cell_text(cells, "rate"))
                items.append({"description": cell_text(cells, "description"), "hsn": cell_text(cells, "hsn") or None,
                              "qty": str(qty.value) if qty else None, "rate": str(rate.value) if rate else None,
                              "amount": str(amt.value), "page": line.page, "bbox": line.bbox})
                res.add(f"item[{len(items)-1}].amount", cell_text(cells, "amount"), str(amt.value), words=cells["amount"])
            break
        res.data["items"] = items
        if items:
            res.data["items_total"] = str(sum((Decimal(i["amount"]) for i in items), Decimal(0)))
        tot = scan_labels(lines, PO_TOTALS, allow_next_line=False)
        if "total" in tot:
            amts = find_amounts(tot["total"][0])
            if amts:
                res.data["total"] = str(amts[-1])
                res.add("total", tot["total"][0], str(amts[-1]), line=tot["total"][1])
        return res