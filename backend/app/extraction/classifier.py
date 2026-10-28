"""Keyword-scored document classifier with abstention. Nothing is keyed on filenames."""
from __future__ import annotations

import re
from dataclasses import dataclass

KEYWORDS: dict[str, list[str]] = {
    "bank_statement": ["account statement", "statement of account", "statement period", "opening balance",
                       "closing balance", "ifsc", "balance", "withdrawal", "deposit", "debit", "credit",
                       "account number", "account no", "narration", "particulars", "transaction"],
    "salary_slip": ["salary slip", "pay slip", "payslip", "earnings", "deductions", "net pay", "net salary",
                    "gross earnings", "provident fund", "professional tax", "paid days", "uan", "basic",
                    "employee code", "hra", "epf"],
    "invoice": ["tax invoice", "invoice no", "invoice number", "invoice date", "gstin", "hsn", "cgst", "sgst",
                "igst", "place of supply", "taxable value", "invoice"],
    "purchase_order": ["purchase order", "po no", "po number", "po date", "vendor", "order total",
                       "delivery date", "ship to", "order value"],
    "employment_letter": ["this is to certify", "employed with", "letter of employment", "to whomsoever it may concern",
                          "salary certificate", "human resources", "authorised signatory", "appointment letter",
                          "offer letter", "employment verification"],
    "pan_card": ["permanent account number", "pan card", "pan details", "income tax", "income tax department", "father's name", "govt. of india", "signature"],
    "aadhaar": ["aadhaar", "uidai", "e-kyc", "unique identification", "resident", "masked aadhaar", "vid", "government of india", "dob", "year of birth", "male", "female", "mera aadhaar", "meri pehchan"],
}
_PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_AADHAAR = re.compile(r"(?<!\d)(\d{4})[ -](\d{4})[ -](\d{4})(?!\d)")
from ..identifiers import verhoeff_valid  # noqa: E402


@dataclass
class Classification:
    doc_type: str
    confidence: float
    scores: dict[str, int]


def classify(text: str, pages=None) -> Classification:  # noqa: ANN001
    t = text.lower()
    scores = {k: sum(1 + p.count(" ") for p in phrases if p in t) for k, phrases in KEYWORDS.items()}
    for m in _AADHAAR.finditer(text):
        if True:  # any 4-4-4 number is a strong card cue; a valid checksum adds a point
            scores["aadhaar"] += 4 if (m.group(1)[0] not in "01" and verhoeff_valid("".join(m.groups()))) else 3
            break
    if _PAN.search(text) and ("permanent account" in t or "income tax" in t):
        scores["pan_card"] += 2
    if pages:
        from ..normalize import is_amount_token, parse_date
        rows = sum(1 for p in pages for ln in p.lines if any(parse_date(w.text) for w in ln.words)
                   and any(is_amount_token(w.text) and ("." in w.text or "," in w.text) for w in ln.words))
        if rows >= 8:
            scores["bank_statement"] += 4
    total = sum(scores.values())
    best = max(scores, key=lambda k: scores[k])
    conf = scores[best] / total if total else 0.0
    if scores[best] < 3 or conf < 0.4:
        return Classification("unknown", round(conf, 3), scores)
    return Classification(best, round(conf, 3), scores)