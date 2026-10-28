"""Single-document security scan: structure, metadata, font-consistency (modification indicators) and
sensitive-information exposure. Every result is an INDICATOR with an explanation; nothing here proves tampering."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import fitz

from .extraction.base import PageText
from .identifiers import GSTIN_RE, IFSC_RE, verhoeff_valid

VERSION = "1.0"
# check -> (points per occurrence, cap). Category decides how the case risk treats it (see engines/forensics.py).
TABLE: dict[str, tuple[int, int, str]] = {
    "launch_action": (40, 40, "structure"), "javascript": (30, 30, "structure"), "embedded_file": (15, 15, "structure"),
    "open_action": (10, 10, "structure"), "additional_actions": (10, 10, "structure"),
    "incremental_update": (10, 30, "modification"), "mixed_font_numeric": (15, 45, "modification"),
    "modified_before_created": (20, 20, "metadata"), "producer_creator_mismatch": (0, 0, "metadata"), "metadata_absent": (0, 0, "metadata"),
    "aadhaar_exposure": (10, 30, "sensitive"), "aadhaar_invalid_exposure": (15, 15, "identifier"), "pan_exposure": (3, 9, "sensitive"), "account_exposure": (3, 9, "sensitive"),
    "gstin_exposure": (0, 0, "sensitive"), "ifsc_exposure": (0, 0, "sensitive"), "mobile_exposure": (2, 6, "sensitive"), "email_exposure": (2, 6, "sensitive"),
}
THRESHOLDS = {"review": 15, "high": 50}
MARGIN = 30.0  # points: headers/footers (page numbers, banners) are ignored by the font check
_PDF_DATE = re.compile(r"D:(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?")
_ACCOUNT = re.compile(r"(?i)(?:a/c|account|acct)[^0-9\n]{0,30}?(\d{9,18})(?!\d)")
_PII = [
    ("aadhaar", re.compile(r"(?<![A-Z0-9])([0-9OQDISBZG]{4})[ -]?([0-9OQDISBZG]{4})[ -]?([0-9OQDISBZG]{4})(?![A-Z0-9])")),
    ("pan", re.compile(r"(?<![A-Z0-9])[A-Z]{5}\d{4}[A-Z](?![A-Z0-9])")),
    ("gstin", GSTIN_RE), ("ifsc", IFSC_RE),
    ("mobile", re.compile(r"(?<![\d+])[6-9]\d{9}(?!\d)")),
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
]


def parse_pdf_date(s: str | None) -> str | None:
    if not s:
        return None
    m = _PDF_DATE.match(s.strip())
    if not m:
        return None
    parts = [int(x) if x else (1 if i < 2 else 0) for i, x in enumerate(m.groups())]
    try:
        return datetime(parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]).isoformat()
    except ValueError:
        return None


def mask(v: str) -> str:
    v = re.sub(r"\s", "", v)
    return v[:2] + "*" * max(1, len(v) - 4) + v[-2:] if len(v) > 4 else "*" * len(v)


def font_family(name: str) -> str:
    n = re.sub(r"^[A-Z]{6}\+", "", name or "")
    return re.split(r"[-,]", n)[0].strip().lower() or "unknown"


class _Acc:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []
        self.used: dict[str, int] = {}

    def add(self, check: str, title: str, explanation: str, **extra: Any) -> None:
        per, cap, category = TABLE[check]
        spent = self.used.get(check, 0)
        pts = max(0, min(per, cap - spent))
        self.used[check] = spent + pts
        self.items.append({"check": check, "category": category, "title": title, "explanation": explanation, "points": pts, **extra})


def scan_document(path: Path, pages: list[PageText], flags: list[str], metadata: dict[str, Any],
                  sha256: str, size: int, content_type: str) -> dict[str, Any]:
    acc = _Acc()
    not_checked: list[dict[str, str]] = []
    is_pdf = content_type == "application/pdf"
    has_text = any(p.words for p in pages)
    raw = path.read_bytes()

    # ---- structure
    structure: dict[str, Any] = {"has_text_layer": has_text, "page_count": len(pages), "encrypted_at_upload": "decrypted_at_upload" in flags}
    if is_pdf:
        inc = max(0, raw.count(b"%%EOF") - 1)
        structure["incremental_updates"] = inc
        for _ in range(inc):
            acc.add("incremental_update", "File has been saved over itself (incremental update)",
                    "The PDF contains more than one end-of-file marker: it was modified and re-saved after creation. Linearised "
                    "files and form fills also produce this; it means 'edited after creation', not 'forged'.")
        for flag in ("javascript", "embedded_file", "open_action", "additional_actions", "launch_action"):
            structure[flag] = flag in flags
            if flag in flags:
                acc.add(flag, f"PDF contains {flag.replace('_', ' ')}",
                        "Active content inside a financial document is unusual and can hide behaviour or payloads. The file was never executed.")
    else:
        structure["incremental_updates"] = None
        not_checked.append({"check": "structure", "reason": "Not a PDF: structural checks apply to PDF files only"})

    # ---- metadata
    meta_out: dict[str, Any] = {"producer": metadata.get("producer"), "creator": metadata.get("creator"),
                                "created": parse_pdf_date(metadata.get("creationDate")), "modified": parse_pdf_date(metadata.get("modDate")),
                                "title": metadata.get("title"), "author": metadata.get("author"), "issues": []}
    if is_pdf:
        if not any(metadata.get(k) for k in ("producer", "creator", "creationDate")):
            meta_out["issues"].append("No producer, creator or creation date recorded")
            acc.add("metadata_absent", "Metadata absent", "Many legitimate generators omit metadata; absence is only notable alongside other indicators.")
        if meta_out["created"] and meta_out["modified"] and meta_out["modified"] < meta_out["created"]:
            meta_out["issues"].append("Modification date precedes creation date")
            acc.add("modified_before_created", "Modification date is earlier than creation date",
                    "Dates in the metadata are inconsistent with each other. Clock errors cause this too, but it is a common trace of edited metadata.")
        p, c = (metadata.get("producer") or "").lower(), (metadata.get("creator") or "").lower()
        if p and c and p.split()[0] != c.split()[0]:
            meta_out["issues"].append("Producer and creator differ")
            acc.add("producer_creator_mismatch", "Producer and creator differ", "The file was created by one application and last written by another, which is normal for converted or printed-to-PDF documents.")
    else:
        not_checked.append({"check": "metadata", "reason": "Not a PDF: no document metadata to inspect"})

    # ---- fonts / modification indicators
    fonts: dict[str, Any] = {"pages": [], "mixed_font_words": []}
    native = any(p.method == "native_pdf" and p.words for p in pages)
    if is_pdf and native:
        with fitz.open(str(path)) as doc:
            for pno, page in enumerate(doc, start=1):
                counts: dict[str, int] = {}
                spans: list[dict[str, Any]] = []
                for block in page.get_text("dict").get("blocks", []):
                    if block.get("type") != 0:
                        continue
                    for line in block.get("lines", []):
                        for sp in line.get("spans", []):
                            text = sp.get("text", "").strip()
                            if not text:
                                continue
                            fam = font_family(sp.get("font", ""))
                            counts[fam] = counts.get(fam, 0) + len(text.split())
                            spans.append({"text": text, "font": sp.get("font", ""), "family": fam, "size": round(float(sp.get("size", 0)), 1), "bbox": [round(v, 1) for v in sp.get("bbox", (0, 0, 0, 0))]})
                dominant = max(counts, key=lambda k: counts[k]) if counts else None
                fonts["pages"].append({"page": pno, "fonts": counts, "dominant_font": dominant})
                h = page.rect.height
                for sp in spans:
                    in_margin = sp["bbox"][1] < MARGIN or sp["bbox"][3] > h - MARGIN
                    if dominant and sp["family"] != dominant and not in_margin and re.search(r"[\dâ‚¹]|Rs\.?", sp["text"]):
                        item = {"page": pno, "text": sp["text"][:60], "font": sp["font"], "size": sp["size"], "bbox": sp["bbox"], "dominant_font": dominant}
                        fonts["mixed_font_words"].append(item)
                        acc.add("mixed_font_numeric", f"Number set in a different font on page {pno}: '{sp['text'][:40]}'",
                                f"Font {sp['font']} differs from the page's dominant font family '{dominant}'. Values edited after the document was "
                                "generated often carry the editor's font. Letterheads and stamps can also do this; this is a potential modification, not proof.",
                                page=pno, bbox=sp["bbox"], value=sp["text"][:60], field="font_check")
    else:
        not_checked.append({"check": "modification_indicators", "reason": "No native text layer (image, scan or OCR input): font information is unavailable, so font consistency cannot be checked"})

    # ---- sensitive information (masked only; raw values are never stored or returned)
    sensitive: list[dict[str, Any]] = []
    if has_text:
        for p in pages:
            for line in p.lines:
                text = line.text
                account_spans = [m.span(1) for m in _ACCOUNT.finditer(text)]
                for s, e in account_spans:
                    sensitive.append({"kind": "account", "masked": mask(text[s:e]), "page": p.number, "bbox": line.bbox})
                for kind, rx in _PII:
                    for m in rx.finditer(text):
                        if any(a <= m.start() < b or a < m.end() <= b for a, b in account_spans):
                            continue
                        val = m.group(0)
                        if kind == "aadhaar":
                            if sum(ch.isdigit() for ch in val) < 6:
                                continue  # a word, not a number
                            digits = re.sub(r"\D", "", val.upper().translate(str.maketrans("OQDISBZG", "00015826")))
                            ctx = text[max(0, m.start() - 30):m.start()].lower()
                            if re.search(r"a/c|account|acct|phone|mobile|txn|ref|uan|epf|pf no|member|policy|invoice|order", ctx):
                                continue
                            if digits[0] in "01" or not verhoeff_valid(digits):
                                if re.search(r"[ -]", val) or re.search(r"aadhaar|uid", ctx):  # only when printed in Aadhaar layout or labelled as one
                                    sensitive.append({"kind": "aadhaar_invalid", "masked": mask(val), "page": p.number, "bbox": line.bbox})
                                continue
                        sensitive.append({"kind": kind, "masked": mask(val), "page": p.number, "bbox": line.bbox})
        seen: set[tuple] = set()
        for s in sensitive:
            key = (s["kind"], s["masked"])
            if key in seen:
                continue
            seen.add(key)
            if s["kind"] == "aadhaar_invalid":
                acc.add("aadhaar_invalid_exposure", f"Aadhaar-format number on page {s['page']} fails the Verhoeff checksum ({s['masked']})",
                        "Every valid Aadhaar number passes the Verhoeff check digit. A 12-digit number in Aadhaar layout that fails it was either misread by OCR "
                        "or is not a valid Aadhaar number. Verify the digits against the document before drawing any conclusion.",
                        page=s["page"], bbox=s["bbox"], value=s["masked"], field="aadhaar_checksum")
                continue
            acc.add(f"{s['kind']}_exposure", f"{s['kind'].upper() if len(s['kind']) <= 5 else s['kind'].title()} present on page {s['page']} ({s['masked']})",
                    "Sensitive identifier found in plain text. Relevant for KYC handling and redaction before sharing; not an indicator of modification.",
                    page=s["page"], bbox=s["bbox"], value=s["masked"], field=f"{s['kind']}_exposure")
    else:
        not_checked.append({"check": "sensitive_information", "reason": "No text could be read (no text layer and OCR unavailable)"})

    score = min(100, sum(i["points"] for i in acc.items))
    level = "Low observed risk" if score < THRESHOLDS["review"] else "Review recommended" if score < THRESHOLDS["high"] else "High observed risk"
    return {
        "version": VERSION, "fingerprint": {"sha256": sha256, "size_bytes": size, "content_type": content_type},
        "structure": structure, "metadata": meta_out, "fonts": fonts,
        "modification_indicators": fonts["mixed_font_words"], "sensitive": sensitive,
        "score": score, "level": level, "thresholds": THRESHOLDS, "contributions": acc.items, "not_checked": not_checked,
        "note": "Scores summarise observed indicators under policy " + VERSION + ". They are not a determination of fraud or tampering.",
    }