from __future__ import annotations

from decimal import Decimal

from ..extraction.base import PageText
from ..extraction.infer_table import infer_transactions
from ..extraction.tables import assign, cell_text, find_table
from ..identifiers import IFSC_RE
from ..normalize import find_dates, parse_amount, parse_date
from .base import DocumentParser, ParseResult, all_lines, letterhead, register, scan_labels

HEADER = {
    "serial": ["sr no", "sr. no", "s no", "s.no", "sl no", "sl. no", "srno", "sno", "#", "sr", "sl"],
    "date": ["date", "txn date", "transaction date", "value date", "tran date", "posting date", "txn. date"],
    "description": ["description", "particulars", "narration", "details", "transaction details",
                    "transaction description", "remarks", "transaction remarks"],
    "ref": ["ref", "ref no", "ref. no", "chq no", "cheque no", "chq/ref no", "chq / ref no", "reference",
            "reference no", "cheque/ref no", "instrument no", "utr"],
    "debit": ["debit", "withdrawal", "withdrawals", "withdrawal (dr)", "debit (dr)", "dr", "withdrawal amt",
              "debit amount", "withdrawal amount", "debits"],
    "credit": ["credit", "deposit", "deposits", "deposit (cr)", "credit (cr)", "cr", "deposit amt",
               "credit amount", "deposit amount", "credits"],
    "amount": ["amount", "amount (inr)", "amount (rs)", "amount (rs.)", "transaction amount", "amount (â‚¹)"],
    "balance": ["balance", "closing balance", "running balance", "balance (inr)", "balance (rs)",
                "available balance", "balance (rs.)"],
}
REQUIRED = [("date",), ("balance",), ("debit", "credit", "amount")]
STOP = ("closing balance", "statement summary", "end of statement", "generated on", "total debit",
        "total credit", "this is a computer", "summary of account")
META = {
    "bank_name": ["bank name"],
    "account_holder": ["account holder name", "account holder", "customer name", "account name", "name of customer", "name"],
    "account_number": ["account number", "account no.", "account no", "a/c no.", "a/c no", "a/c number", "acct no"],
    "ifsc": ["ifsc code", "ifsc"],
    "branch": ["branch name", "branch"],
    "period": ["statement period", "period", "statement for the period", "statement date range"],
    "opening_balance": ["opening balance"],
    "closing_balance": ["closing balance"],
    "currency": ["currency"],
}


def _s(a: Decimal | None) -> str | None:
    return None if a is None else str(a)


@register
class BankStatementParser(DocumentParser):
    doc_type = "bank_statement"

    def parse(self, pages: list[PageText]) -> ParseResult:
        res = ParseResult(self.doc_type)
        lines = all_lines(pages)
        bank, bank_line = letterhead(lines)
        res.add("bank_name", bank, line=bank_line, confidence=0.7)
        meta = scan_labels(lines, META, allow_next_line=False)
        for key in ("account_holder", "account_number", "ifsc", "branch", "currency"):
            if key in meta:
                val, line = meta[key]
                res.add(key, val, line=line)
                res.data[key] = val
        if "ifsc" not in res.data:
            m = IFSC_RE.search(" ".join(line.text for line in lines[:40]))
            if m:
                res.data["ifsc"] = m.group(1)
                res.add("ifsc", m.group(1), confidence=0.85)
        if "period" in meta:
            ds = find_dates(meta["period"][0])
            if len(ds) >= 2:
                res.data["period_from"], res.data["period_to"] = ds[0].isoformat(), ds[1].isoformat()
                res.add("period_from", ds[0].isoformat(), line=meta["period"][1])
                res.add("period_to", ds[1].isoformat(), line=meta["period"][1])
        for key in ("opening_balance", "closing_balance"):
            if key in meta:
                a = parse_amount(meta[key][0].split()[0]) if meta[key][0] else None
                if a:
                    res.data[key] = str(a.value)
                    res.add(key, meta[key][0], str(a.value), line=meta[key][1])

        txns: list[dict] = []
        prev_balance: Decimal | None = Decimal(res.data["opening_balance"]) if "opening_balance" in res.data else None
        header_found = False
        for page in pages:
            found = find_table(page.lines, HEADER, REQUIRED)
            if not found:
                continue
            header_found = True
            idx, cols = found
            keys = {c.key for c in cols}
            current: dict | None = None
            for line in page.lines[idx + 1:]:
                low = line.text.lower()
                if any(s in low for s in STOP):
                    if "closing balance" in low:
                        amts = [parse_amount(w.text) for w in line.words]
                        amts = [a for a in amts if a]
                        if amts:
                            res.data["closing_balance"] = str(amts[-1].value)
                            res.add("closing_balance", line.text, str(amts[-1].value), line=line)
                    break
                cells = assign(line, cols)
                d = parse_date(cell_text(cells, "date"))
                debit = parse_amount(cell_text(cells, "debit")) if "debit" in keys else None
                credit = parse_amount(cell_text(cells, "credit")) if "credit" in keys else None
                amount = parse_amount(cell_text(cells, "amount")) if "amount" in keys else None
                balance = parse_amount(cell_text(cells, "balance"))
                has_amt = any(x is not None for x in (debit, credit, amount, balance))
                if d is not None and has_amt:
                    desc = cell_text(cells, "description")
                    if "opening balance" in desc.lower() and balance is not None:
                        prev_balance = balance.value
                        res.data.setdefault("opening_balance", str(balance.value))
                        current = None
                        continue
                    dr, cr, inferred, conf = (debit.value if debit else None), (credit.value if credit else None), False, 0.95
                    if amount is not None:
                        v = amount.value
                        if amount.direction == "CR":
                            cr = abs(v)
                        elif amount.direction == "DR" or v < 0:
                            dr = abs(v)
                        elif prev_balance is not None and balance is not None:
                            delta = balance.value - prev_balance
                            if abs(delta - v) < Decimal("0.01"):
                                cr, inferred = v, True
                            elif abs(delta + v) < Decimal("0.01"):
                                dr, inferred = v, True
                            else:
                                cr, inferred, conf = v, True, 0.6
                        else:
                            cr, inferred, conf = v, True, 0.6
                        if inferred:
                            conf = min(conf, 0.75)
                    row = {
                        "index": len(txns), "serial": cell_text(cells, "serial") or None, "date": d.isoformat(),
                        "description": desc, "ref": cell_text(cells, "ref") or None,
                        "debit": _s(dr), "credit": _s(cr), "balance": _s(balance.value) if balance else None,
                        "direction_inferred": inferred, "page": line.page, "bbox": line.bbox, "confidence": conf,
                    }
                    txns.append(row)
                    current = row
                    i = row["index"]
                    res.add(f"txn[{i}].date", cell_text(cells, "date"), d.isoformat(), words=cells["date"], confidence=conf)
                    for k, val in (("debit", dr), ("credit", cr)):
                        if val is not None:
                            src = cells.get(k) or cells.get("amount", [])
                            res.add(f"txn[{i}].{k}", cell_text(cells, k) or cell_text(cells, "amount"), str(val), words=src, confidence=conf)
                    if balance:
                        res.add(f"txn[{i}].balance", cell_text(cells, "balance"), str(balance.value), words=cells["balance"], confidence=conf)
                        prev_balance = balance.value
                elif current is not None and not has_amt and d is None and cells.get("description") \
                        and len(cells["description"]) >= 0.8 * len(line.words):
                    current["description"] = (current["description"] + " " + cell_text(cells, "description")).strip()
                    current["bbox"] = [min(current["bbox"][0], line.bbox[0]), min(current["bbox"][1], line.bbox[1]),
                                       max(current["bbox"][2], line.bbox[2]), max(current["bbox"][3], line.bbox[3])]
        if not header_found or not txns:
            opening = Decimal(res.data["opening_balance"]) if "opening_balance" in res.data else None
            inferred, notes, opening = infer_transactions(pages, opening)
            res.warnings.extend(notes)
            if inferred:
                txns = inferred
                res.warnings.append("Transaction table inferred from column geometry and balance arithmetic; no header row was recognised")
                if opening is not None and "opening_balance" not in res.data:
                    res.data["opening_balance"] = str(opening)
                for row in txns:
                    i, cells = row["index"], row.pop("_cells", {})
                    res.add(f"txn[{i}].date", row["date"], row["date"], confidence=row["confidence"], page=row["page"], bbox=cells.get("date"))
                    if row["debit"] is not None:
                        res.add(f"txn[{i}].debit", row["debit"], row["debit"], confidence=row["confidence"], page=row["page"], bbox=cells.get("a") or cells.get("b"))
                    if row["credit"] is not None:
                        res.add(f"txn[{i}].credit", row["credit"], row["credit"], confidence=row["confidence"], page=row["page"], bbox=cells.get("b") or cells.get("a"))
                    res.add(f"txn[{i}].balance", row["balance"], row["balance"], confidence=row["confidence"], page=row["page"], bbox=cells.get("balance"))
            elif not header_found:
                res.warnings.append("No transaction table header recognised")
        res.data["transactions"] = txns
        res.data["transaction_count"] = len(txns)
        if "closing_balance" not in res.data and txns and txns[-1]["balance"]:
            res.data["closing_balance"] = txns[-1]["balance"]
        res.add("transaction_count", len(txns), confidence=0.9)
        return res