from __future__ import annotations

import re
from decimal import Decimal

from ..extraction.base import PageText
from ..extraction.tables import assign, cell_text, find_table
from ..identifiers import GSTIN_RE
from ..normalize import find_amounts, find_date, parse_amount
from .base import DocumentParser, ParseResult, all_lines, full_text, letterhead, register, scan_labels

ITEM_HEADER = {
    "serial": ["sr no", "sr. no", "s no", "s.no", "sl no", "#", "sno"],
    "description": ["description", "item description", "item", "particulars", "product", "description of goods",
                    "description of goods / services", "goods/services"],
    "hsn": ["hsn", "hsn/sac", "hsn / sac", "hsn code", "sac", "hsn/sac code"],
    "qty": ["qty", "quantity", "qty."],
    "rate": ["rate", "unit price", "price", "rate (inr)", "unit rate"],
    "amount": ["amount", "amount (inr)", "total", "value", "line total", "taxable value", "amount (rs.)"],
}
ITEM_REQUIRED = [("description",), ("amount",)]
ITEM_STOP = ("sub total", "subtotal", "taxable", "cgst", "sgst", "igst", "total", "amount in words", "grand")
META = {
    "invoice_number": ["invoice no.", "invoice no", "invoice number", "invoice #", "inv no", "inv. no", "bill no"],
    "invoice_date": ["invoice date", "date of invoice", "dated", "date"],
    "po_ref": ["po ref", "po no", "po number", "purchase order no", "order ref", "buyer's order no", "po reference"],
    "place_of_supply": ["place of supply"],
    "due_date": ["due date", "payment due"],
    "buyer": ["bill to", "billed to", "buyer", "customer", "billing address", "details of receiver"],
    "gstin_line": ["gstin/uin", "gstin"],
}
TOTALS = {
    "taxable_value": ["taxable value", "sub total", "subtotal", "taxable amount", "total taxable"],
    "cgst": ["cgst"], "sgst": ["sgst"], "igst": ["igst"],
    "total": ["grand total", "invoice total", "total amount", "total payable", "amount payable", "net payable", "total"],
}


@register
class InvoiceParser(DocumentParser):
    doc_type = "invoice"

    def parse(self, pages: list[PageText]) -> ParseResult:
        res = ParseResult(self.doc_type)
        lines = all_lines(pages)
        supplier, sl = letterhead([ln for ln in lines if not re.fullmatch(r"\s*tax invoice\s*|\s*invoice\s*", ln.text, re.I)])
        res.add("supplier", supplier, line=sl, confidence=0.7)
        res.data["supplier"] = supplier
        gstins = [m.group(1) for m in GSTIN_RE.finditer(full_text(pages))]
        if gstins:
            res.data["supplier_gstin"] = gstins[0]
            res.add("supplier_gstin", gstins[0], confidence=0.85)
        if len(gstins) > 1:
            res.data["buyer_gstin"] = gstins[1]
            res.add("buyer_gstin", gstins[1], confidence=0.8)
        meta = scan_labels(lines, META)
        for key in ("invoice_number", "po_ref", "place_of_supply", "buyer"):
            if key in meta and meta[key][0]:
                val = re.split(r"\s{2,}|\s+gstin", meta[key][0], flags=re.I)[0].strip()
                res.data[key] = val
                res.add(key, val, line=meta[key][1])
        for key in ("invoice_date", "due_date"):
            if key in meta:
                d = find_date(meta[key][0])
                if d:
                    res.data[key] = d.isoformat()
                    res.add(key, meta[key][0], d.isoformat(), line=meta[key][1])

        items: list[dict] = []
        for page in pages:
            found = find_table(page.lines, ITEM_HEADER, ITEM_REQUIRED)
            if not found:
                continue
            idx, cols = found
            for line in page.lines[idx + 1:]:
                low = line.text.lower()
                if any(s in low for s in ITEM_STOP):
                    break
                cells = assign(line, cols)
                amt = parse_amount(cell_text(cells, "amount"))
                desc = cell_text(cells, "description")
                if amt is None:
                    if items and desc and not any(cells.get(k) for k in ("qty", "rate", "hsn")):
                        items[-1]["description"] += " " + desc
                    continue
                qty = parse_amount(cell_text(cells, "qty"))
                rate = parse_amount(cell_text(cells, "rate"))
                items.append({"description": desc, "hsn": cell_text(cells, "hsn") or None,
                              "qty": str(qty.value) if qty else None, "rate": str(rate.value) if rate else None,
                              "amount": str(amt.value), "page": line.page, "bbox": line.bbox})
                i = len(items) - 1
                res.add(f"item[{i}].amount", cell_text(cells, "amount"), str(amt.value), words=cells["amount"])
                if qty and rate:
                    res.add(f"item[{i}].qty", cell_text(cells, "qty"), str(qty.value), words=cells["qty"])
                    res.add(f"item[{i}].rate", cell_text(cells, "rate"), str(rate.value), words=cells["rate"])
            break
        res.data["items"] = items
        if items:
            res.data["items_total"] = str(sum((Decimal(i["amount"]) for i in items), Decimal(0)))

        totals = scan_labels(lines, TOTALS, allow_next_line=False)
        for key, (val, line) in totals.items():
            amts = find_amounts(val)
            if amts:
                res.data[key] = str(amts[-1])
                res.add(key, val, str(amts[-1]), line=line)
                m = re.search(r"(\d+(?:\.\d+)?)\s*%", val)
                if m and key in ("cgst", "sgst", "igst"):
                    res.data[f"{key}_rate"] = m.group(1)
        if "total" not in res.data:
            res.warnings.append("Invoice total not found")
        return res