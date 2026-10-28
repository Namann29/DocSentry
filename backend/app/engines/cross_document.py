from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal

from ..normalize import format_inr as inr
from .base import Context, DocView, FindingDTO, ev, rule
from .financial import LOW_CONF, TOL, D, salary_credits

STOP_TOKENS = {"PVT", "LTD", "PRIVATE", "LIMITED", "LLP", "INC", "THE", "AND", "CO", "COMPANY"}


def _tokens(name: str) -> set[str]:
    return {t for t in re.findall(r"[A-Z]{4,}", name.upper()) if t not in STOP_TOKENS}


def _payments_to(b: DocView, party: str) -> list[dict]:
    toks = _tokens(party)
    out = []
    for t in b.get("transactions", []):
        if not t.get("debit"):
            continue
        desc = t.get("description", "").upper()
        if (toks and any(tok in desc for tok in toks)) or "INV" in desc:
            out.append(t)
    return out


@rule("cross_document", requires=("salary_slip", "bank_statement"), description="Salary slip net pay vs salary credit in the bank statement")
def salary_vs_bank(ctx: Context) -> list[FindingDTO]:
    s, b = ctx.first("salary_slip"), ctx.first("bank_statement")
    net, month = s.amount("net_pay"), s.get("month")
    if net is None:
        return [FindingDTO("cross_document", "cross_document.salary_vs_bank", 6, "low", "Salary comparison not possible: net pay not extracted", "", [ev(s, "net_pay", None)])]
    creds = salary_credits(b.get("transactions", []))
    in_month = [t for t in creds if month and t["date"].startswith(month)]
    pf, pt = b.get("period_from"), b.get("period_to")
    if not in_month:
        if month and pf and pt and not (pf[:7] <= month <= pt[:7]):
            return [FindingDTO("cross_document", "cross_document.salary_vs_bank", 6, "info", f"Statement period {pf} to {pt} does not cover salary month {month}",
                               "Comparison skipped; request a statement covering the slip month.", [ev(s, "month", month), ev(b, "period_from", pf)])]
        return [FindingDTO("cross_document", "cross_document.salary_vs_bank", 3, "medium", f"No salary-like credit found in the statement for {month or 'the slip month'}",
                           f"The slip states net pay {inr(net)} but no matching credit was identified in that month.", [ev(s, "net_pay", net), ev(b, "transactions", len(creds))])]
    t = max(in_month, key=lambda x: Decimal(x["credit"]))
    credit = Decimal(t["credit"])
    diff = net - credit
    conf = min(s.confidence("net_pay"), t.get("confidence", 0.95))
    suspect = conf < LOW_CONF
    evid = [ev(s, "net_pay", net, 1), ev(b, f"txn[{t['index']}].credit", credit, t.get("page"), date=t["date"], description=t.get("description"), bbox=t.get("bbox"))]
    if abs(diff) <= max(Decimal("1.00"), net * Decimal("0.01")):
        return [FindingDTO("cross_document", "cross_document.salary_vs_bank", 3, "info", f"Salary credit {inr(credit)} on {t['date']} matches slip net pay {inr(net)}", "", evid)]
    title = f"Salary slip reports net pay {inr(net)}; bank statement shows salary credit {inr(credit)} on {t['date']}. Discrepancy: {inr(abs(diff))}"
    return [FindingDTO("cross_document", "cross_document.salary_vs_bank", 3, "medium" if suspect else "high",
                       ("Possible extraction error: " if suspect else "") + title,
                       "The credited amount is " + ("lower" if diff > 0 else "higher") + " than the slip's net pay. Possible causes: altered slip, partial payment, "
                       "salary split across accounts, or an extraction error." + (" Low extraction confidence on an involved field." if suspect else ""),
                       evid, possible_extraction_error=suspect)]


@rule("cross_document", requires=("salary_slip", "employment_letter"), description="Salary figures in the employment letter vs the salary slip")
def letter_vs_slip(ctx: Context) -> list[FindingDTO]:
    s, l = ctx.first("salary_slip"), ctx.first("employment_letter")
    out: list[FindingDTO] = []
    for lk, sk, label in (("net_monthly_salary", "net_pay", "net"), ("gross_monthly_salary", "gross", "gross")):
        lv, sv = l.amount(lk), s.amount(sk)
        if lv is None or sv is None:
            continue
        if abs(lv - sv) > TOL:
            out.append(FindingDTO("cross_document", "cross_document.letter_vs_slip", 3, "medium", f"Employment letter {label} salary {inr(lv)} differs from slip {label} {inr(sv)}",
                                  f"Difference {inr(abs(lv - sv))}.", [ev(l, lk, lv), ev(s, sk, sv)]))
        else:
            out.append(FindingDTO("cross_document", "cross_document.letter_vs_slip", 3, "info", f"Employment letter {label} salary matches slip ({inr(sv)})", "", [ev(l, lk, lv), ev(s, sk, sv)]))
    return out


@rule("cross_document", requires=("invoice",), description="Duplicate invoice numbers with differing amounts")
def duplicate_invoice_numbers(ctx: Context) -> list[FindingDTO]:
    groups: dict[str, list[DocView]] = defaultdict(list)
    for inv in ctx.of("invoice"):
        if inv.get("invoice_number"):
            groups[inv["data"]["invoice_number"].strip().upper() if isinstance(inv, dict) else inv.get("invoice_number").strip().upper()].append(inv)
    out: list[FindingDTO] = []
    for num, invs in groups.items():
        if len(invs) < 2:
            continue
        totals = [inv.amount("total") for inv in invs]
        evid = [ev(inv, "total", t, 1, invoice_number=num) for inv, t in zip(invs, totals)]
        if len({t for t in totals if t is not None}) > 1:
            out.append(FindingDTO("cross_document", "cross_document.duplicate_invoice_numbers", 3, "high",
                                  f"Two invoices share number {num} but differ in amount: " + " vs ".join(inr(t) if t is not None else "?" for t in totals),
                                  "The same invoice number was issued with different totals. Possible altered copy, re-issued invoice, or duplicate billing.", evid))
        else:
            out.append(FindingDTO("cross_document", "cross_document.duplicate_invoice_numbers", 3, "low", f"Invoice number {num} appears {len(invs)} times with the same total",
                                  "Likely duplicate copies of one invoice.", evid))
    return out


@rule("cross_document", requires=("invoice", "purchase_order"), description="Invoice total vs linked purchase order")
def invoice_vs_po(ctx: Context) -> list[FindingDTO]:
    out: list[FindingDTO] = []
    pos = {p.get("po_number", "").strip().upper(): p for p in ctx.of("purchase_order") if p.get("po_number")}
    for inv in ctx.of("invoice"):
        ref = (inv.get("po_ref") or "").strip().upper()
        po = pos.get(ref)
        if not po:
            out.append(FindingDTO("cross_document", "cross_document.invoice_vs_po", 6, "low", f"Invoice {inv.get('invoice_number', '?')} references PO '{ref or '-'}' which is not in the case",
                                  "Cannot reconcile without the purchase order.", [ev(inv, "po_ref", ref)]))
            continue
        it, pt = inv.amount("total"), po.amount("total")
        if it is None or pt is None:
            continue
        if abs(it - pt) > TOL:
            out.append(FindingDTO("cross_document", "cross_document.invoice_vs_po", 3, "medium", f"Invoice {inv.get('invoice_number')} total {inr(it)} vs PO {ref} total {inr(pt)}: difference {inr(abs(it - pt))}",
                                  "Invoiced amount does not match the purchase order.", [ev(inv, "total", it), ev(po, "total", pt)]))
        else:
            out.append(FindingDTO("cross_document", "cross_document.invoice_vs_po", 3, "info", f"Invoice {inv.get('invoice_number')} matches PO {ref} ({inr(pt)})", "", [ev(inv, "total", it), ev(po, "total", pt)]))
    return out


@rule("cross_document", requires=("invoice", "bank_statement"), description="Invoice total vs payment found in the bank statement")
def invoice_vs_payment(ctx: Context) -> list[FindingDTO]:
    out: list[FindingDTO] = []
    b = ctx.first("bank_statement")
    for inv in ctx.of("invoice"):
        total = inv.amount("total")
        if total is None:
            continue
        pays = _payments_to(b, inv.get("supplier", ""))
        exact = [t for t in pays if abs(Decimal(t["debit"]) - total) <= TOL]
        num = inv.get("invoice_number", "?")
        if exact:
            t = exact[0]
            out.append(FindingDTO("cross_document", "cross_document.invoice_vs_payment", 3, "info", f"Payment of {inr(total)} on {t['date']} matches invoice {num}", "",
                                  [ev(inv, "total", total), ev(b, f"txn[{t['index']}].debit", t["debit"], t.get("page"), date=t["date"])]))
        elif pays:
            t = max(pays, key=lambda x: Decimal(x["debit"]))
            paid = Decimal(t["debit"])
            diff = paid - total
            word = "exceeds" if diff > 0 else "is short of"
            out.append(FindingDTO("cross_document", "cross_document.invoice_vs_payment", 3, "medium",
                                  f"Payment {inr(paid)} on {t['date']} {word} invoice {num} total {inr(total)} by {inr(abs(diff))}" + (": possible overpayment" if diff > 0 else ""),
                                  "A debit to the supplier was found but its amount does not equal the invoice total.",
                                  [ev(inv, "total", total), ev(b, f"txn[{t['index']}].debit", paid, t.get("page"), date=t["date"], description=t.get("description"))]))
        else:
            out.append(FindingDTO("cross_document", "cross_document.invoice_vs_payment", 6, "info", f"No payment to the supplier of invoice {num} found in the statement",
                                  "The invoice may be unpaid or paid from another account.", [ev(inv, "total", total)]))
    return out


@rule("cross_document", requires=("purchase_order", "bank_statement"), description="Purchase order value vs payment to the vendor")
def po_vs_payment(ctx: Context) -> list[FindingDTO]:
    out: list[FindingDTO] = []
    b = ctx.first("bank_statement")
    for po in ctx.of("purchase_order"):
        total = po.amount("total")
        if total is None:
            continue
        pays = _payments_to(b, po.get("vendor", ""))
        if not pays:
            continue
        t = max(pays, key=lambda x: Decimal(x["debit"]))
        paid = Decimal(t["debit"])
        if paid - total > TOL:
            out.append(FindingDTO("cross_document", "cross_document.po_vs_payment", 3, "medium",
                                  f"Payment {inr(paid)} exceeds PO {po.get('po_number')} value {inr(total)} by {inr(paid - total)}: possible overpayment",
                                  "The amount paid to the vendor is higher than the purchase order authorises.",
                                  [ev(po, "total", total), ev(b, f"txn[{t['index']}].debit", paid, t.get("page"), date=t["date"])]))
        elif abs(paid - total) <= TOL:
            out.append(FindingDTO("cross_document", "cross_document.po_vs_payment", 3, "info", f"Payment {inr(paid)} equals PO {po.get('po_number')} value", "",
                                  [ev(po, "total", total), ev(b, f"txn[{t['index']}].debit", paid, t.get("page"))]))
    return out


@rule("cross_document", requires=("salary_slip", "bank_statement"), description="Period coverage: slip month within statement period")
def period_coverage(ctx: Context) -> list[FindingDTO]:
    s, b = ctx.first("salary_slip"), ctx.first("bank_statement")
    month, pf, pt = s.get("month"), b.get("period_from"), b.get("period_to")
    if not (month and pf and pt):
        return []
    inside = pf[:7] <= month <= pt[:7]
    return [FindingDTO("cross_document", "cross_document.period_coverage", 3, "info" if inside else "low",
                       f"Salary month {month} is {'within' if inside else 'outside'} the statement period {pf} to {pt}", "",
                       [ev(s, "month", month), ev(b, "period_from", pf), ev(b, "period_to", pt)])]