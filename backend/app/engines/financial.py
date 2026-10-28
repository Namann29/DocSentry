from __future__ import annotations

import re
from collections import Counter, defaultdict
from decimal import Decimal
from statistics import median

from ..identifiers import validate_gstin
from ..normalize import format_inr as inr
from .base import Context, DocView, FindingDTO, ev, rule

TOL = Decimal("0.02")
LOW_CONF = 0.7
SALARY_RE = re.compile(r"\bSAL(?:ARY)?\b|PAYROLL|NEFT-SAL", re.I)


def D(v) -> Decimal | None:  # noqa: N802
    return Decimal(str(v)) if v not in (None, "") else None


def repair_candidates(expected: Decimal, observed: str) -> list[str]:
    """Single-digit substitutions of the observed value that would reconcile. Suggestions only, never applied."""
    out = []
    for i, ch in enumerate(observed):
        if not ch.isdigit():
            continue
        for d in "0123456789":
            if d != ch:
                cand = observed[:i] + d + observed[i + 1:]
                try:
                    if Decimal(cand) == expected:
                        out.append(cand)
                except Exception:
                    pass
    return out


def salary_credits(txns: list[dict]) -> list[dict]:
    """Credits that look like salary: description pattern first, else amounts recurring across months."""
    hits = [t for t in txns if t.get("credit") and SALARY_RE.search(t.get("description", ""))]
    if hits:
        return hits
    by_amount: dict[str, set[str]] = defaultdict(set)
    for t in txns:
        if t.get("credit"):
            by_amount[t["credit"]].add(t["date"][:7])
    recurring = {a for a, months in by_amount.items() if len(months) >= 2}
    return [t for t in txns if t.get("credit") in recurring]


@rule("financial", requires=("bank_statement",), description="Running balance reconciliation with extraction-error detection")
def running_balance(ctx: Context) -> list[FindingDTO]:
    out: list[FindingDTO] = []
    for b in ctx.of("bank_statement"):
        txns = b.get("transactions", [])
        prev = D(b.get("opening_balance"))
        inferred = sum(1 for t in txns if t.get("direction_inferred"))
        i = 0
        while i < len(txns):
            t = txns[i]
            bal = D(t.get("balance"))
            if prev is None or bal is None:
                prev = bal if bal is not None else prev
                i += 1
                continue
            expected = prev + (D(t.get("credit")) or 0) - (D(t.get("debit")) or 0)
            if abs(expected - bal) <= TOL:
                prev = bal
                i += 1
                continue
            isolated = False
            if i + 1 < len(txns) and D(txns[i + 1].get("balance")) is not None:
                nxt = txns[i + 1]
                if abs(expected + (D(nxt.get("credit")) or 0) - (D(nxt.get("debit")) or 0) - D(nxt.get("balance"))) <= TOL:
                    isolated = True
            conf = min(t.get("confidence", 0.95), txns[i - 1].get("confidence", 0.95) if i else 0.95)
            suspect = conf < LOW_CONF
            cands = repair_candidates(expected, str(bal))
            row = i + 1
            title = (f"Running balance on row {row} does not follow from row {row - 1}: expected {inr(expected)}, shown {inr(bal)}"
                     if i else f"Row 1 balance {inr(bal)} does not follow from opening balance: expected {inr(expected)}")
            if suspect:
                title = "Possible extraction error: " + title[0].lower() + title[1:]
            expl = (f"Difference {inr(bal - expected)}. " + ("The next row reconciles with the expected value, so this looks like an isolated error in this row. " if isolated else
                    "Subsequent rows chain from the shown value. ") + (f"Repair candidates (single-digit changes that would reconcile): {', '.join(cands)}. Shown as suggestions only; nothing was applied. " if cands else "")
                    + ("Involved fields have low extraction confidence; needs human check." if suspect else ""))
            out.append(FindingDTO("financial", "financial.running_balance", 2, "medium" if suspect else "high", title, expl,
                                  [ev(b, f"txn[{i}].balance", bal, t.get("page"), row=row, expected=str(expected), repair_candidates=cands, bbox=t.get("bbox")),
                                   ev(b, f"txn[{i - 1}].balance" if i else "opening_balance", prev)], possible_extraction_error=suspect))
            prev = expected if isolated else bal
            i += 1
        if txns and not out:
            out.append(FindingDTO("financial", "financial.running_balance", 2, "info", f"Running balance reconciles across {len(txns)} transactions", "",
                                  [ev(b, "transaction_count", len(txns))]))
        if inferred:
            out.append(FindingDTO("financial", "financial.running_balance", 6, "info", f"{inferred} rows had debit/credit direction inferred from balance arithmetic",
                                  "Single amount column without Cr/Dr marker; direction was resolved arithmetically and is flagged in the extraction review.",
                                  [ev(b, "transactions", inferred)]))
    return out


@rule("financial", requires=("bank_statement",), description="Duplicate transactions and serial-number gaps")
def duplicates_and_serials(ctx: Context) -> list[FindingDTO]:
    out: list[FindingDTO] = []
    for b in ctx.of("bank_statement"):
        txns = b.get("transactions", [])
        seen = Counter((t.get("date"), t.get("description"), t.get("debit"), t.get("credit")) for t in txns)
        for key, n in seen.items():
            if n > 1:
                out.append(FindingDTO("financial", "financial.duplicates_and_serials", 2, "low", f"Transaction repeated {n} times: {key[0]} {key[1][:40]}",
                                      "Identical date, description and amount. Could be a legitimate repeat or a copied row.",
                                      [ev(b, f"txn[{i}]", key[1]) for i, t in enumerate(txns) if (t.get("date"), t.get("description"), t.get("debit"), t.get("credit")) == key]))
        serials = [int(t["serial"]) for t in txns if t.get("serial") and str(t["serial"]).isdigit()]
        if len(serials) >= 3:
            gaps = [(a, c) for a, c in zip(serials, serials[1:]) if c != a + 1]
            if gaps:
                out.append(FindingDTO("financial", "financial.duplicates_and_serials", 2, "low", f"Serial numbers are not contiguous ({len(gaps)} gap(s))",
                                      f"Examples: {gaps[:3]}. Rows may be missing or the extraction may have skipped rows.", [ev(b, "transactions", str(gaps[:3]))]))
    return out


@rule("financial", requires=("bank_statement",), description="Income identification and statistical outliers (not fraud)")
def income_and_outliers(ctx: Context) -> list[FindingDTO]:
    out: list[FindingDTO] = []
    for b in ctx.of("bank_statement"):
        txns = b.get("transactions", [])
        sal = salary_credits(txns)
        if sal:
            out.append(FindingDTO("financial", "financial.income_and_outliers", 2, "info",
                                  f"{len(sal)} salary-like credit(s) identified: " + ", ".join(f"{t['date']} {inr(Decimal(t['credit']))}" for t in sal[:6]),
                                  "Matched by description pattern or monthly recurrence.", [ev(b, f"txn[{t['index']}].credit", t["credit"], t.get("page")) for t in sal]))
        debits = [D(t["debit"]) for t in txns if t.get("debit")]
        if len(debits) >= 8:
            med = median(debits)
            for t in txns:
                d = D(t.get("debit"))
                if d and med and d > 5 * med:
                    out.append(FindingDTO("financial", "financial.income_and_outliers", 6, "info",
                                          f"Statistical outlier debit {inr(d)} on {t['date']} (>5x median {inr(med)})",
                                          "A statistically unusual transaction is not a fraudulent transaction; listed for context only.",
                                          [ev(b, f"txn[{t['index']}].debit", d, t.get("page"))]))
    return out


@rule("financial", requires=("salary_slip",), description="Salary slip arithmetic: earnings, deductions and net pay")
def salary_slip_arithmetic(ctx: Context) -> list[FindingDTO]:
    out: list[FindingDTO] = []
    for s in ctx.of("salary_slip"):
        gross, ded, net = s.amount("gross"), s.amount("total_deductions"), s.amount("net_pay")
        et, dt = s.amount("earnings_total"), s.amount("deductions_total")
        checks = []
        if gross is not None and ded is not None and net is not None:
            checks.append(("gross - deductions = net", gross - ded, net, "net_pay"))
        if gross is not None and et is not None and et > 0:
            checks.append(("sum of earnings = gross", et, gross, "gross"))
        if ded is not None and dt is not None and dt > 0:
            checks.append(("sum of deductions = total deductions", dt, ded, "total_deductions"))
        bad = False
        for label, computed, stated, fld in checks:
            if abs(computed - stated) > TOL:
                bad = True
                low = s.confidence(fld) < LOW_CONF
                out.append(FindingDTO("financial", "financial.salary_slip_arithmetic", 2, "medium" if not low else "low",
                                      ("Possible extraction error: " if low else "") + f"Salary slip {label} fails: computed {inr(computed)}, stated {inr(stated)}",
                                      f"Difference {inr(computed - stated)}.", [ev(s, fld, stated, repair_candidates=repair_candidates(computed, str(stated)))],
                                      possible_extraction_error=low))
        if checks and not bad:
            out.append(FindingDTO("financial", "financial.salary_slip_arithmetic", 2, "info", f"Salary slip arithmetic consistent (net {inr(net) if net is not None else '-'})", "",
                                  [ev(s, "net_pay", net)]))
        if not checks:
            out.append(FindingDTO("financial", "financial.salary_slip_arithmetic", 6, "low", "Salary slip totals could not be checked",
                                  "Gross, deductions or net pay were not extracted.", [ev(s, "net_pay", net)]))
    return out


@rule("financial", requires=("invoice",), description="Invoice line arithmetic, tax split and GSTIN checks")
def invoice_arithmetic(ctx: Context) -> list[FindingDTO]:
    out: list[FindingDTO] = []
    for inv in ctx.of("invoice"):
        items_total, taxable, total = inv.amount("items_total"), inv.amount("taxable_value"), inv.amount("total")
        cgst, sgst, igst = inv.amount("cgst") or Decimal(0), inv.amount("sgst") or Decimal(0), inv.amount("igst") or Decimal(0)
        probs = []
        if taxable is not None and items_total is not None and inv.get("items") and abs(items_total - taxable) > TOL:
            probs.append(f"line items sum to {inr(items_total)} but taxable value is {inr(taxable)}")
        for key, rate_key, amt in (("cgst", "cgst_rate", cgst), ("sgst", "sgst_rate", sgst), ("igst", "igst_rate", igst)):
            rate = inv.get(rate_key)
            if rate and taxable is not None and abs((taxable * Decimal(rate) / 100).quantize(Decimal("0.01")) - amt) > TOL:
                probs.append(f"{key.upper()} {inr(amt)} is not {rate}% of {inr(taxable)}")
        if taxable is not None and total is not None and abs(taxable + cgst + sgst + igst - total) > TOL:
            probs.append(f"total {inr(total)} differs from taxable + tax = {inr(taxable + cgst + sgst + igst)}")
        if probs:
            out.append(FindingDTO("financial", "financial.invoice_arithmetic", 2, "medium", f"Invoice {inv.get('invoice_number', '?')} arithmetic fails",
                                  "; ".join(probs) + ".", [ev(inv, "total", total), ev(inv, "taxable_value", taxable)]))
        elif total is not None:
            out.append(FindingDTO("financial", "financial.invoice_arithmetic", 2, "info", f"Invoice {inv.get('invoice_number', '?')} arithmetic consistent (total {inr(total)})", "",
                                  [ev(inv, "total", total)]))
        for key in ("supplier_gstin", "buyer_gstin"):
            g = inv.get(key)
            if g:
                chk = validate_gstin(g)
                sev = "info" if chk.checksum_valid else "medium"
                out.append(FindingDTO("financial", "financial.invoice_arithmetic", 1, sev,
                                      f"{key.replace('_', ' ').title()} {g} {'passes' if chk.checksum_valid else 'fails'} structure/checksum",
                                      "Checksum validity is a format property; registration status was not verified externally.", [ev(inv, key, g)]))
    return out