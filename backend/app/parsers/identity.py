from __future__ import annotations

import re

from ..config import settings
from ..extraction.base import PageText
from ..identifiers import (AADHAAR_FULL_RE, AADHAAR_MASKED_RE, PAN_RE, aadhaar_token, validate_aadhaar,
                           validate_pan)
from ..identifiers import repair_pan
from ..normalize import find_date
from .base import DocumentParser, ParseResult, all_lines, full_text, register, scan_labels

PAN_META = {
    "name": ["name"],
    "father_name": ["father's name", "father name", "fathers name", "father"],
    "dob": ["date of birth", "dob", "birth"],
    "pan": ["permanent account number", "pan no", "pan"],
}
AADHAAR_META = {
    "name": ["name"],
    "dob": ["date of birth", "dob", "year of birth", "yob"],
    "gender": ["gender", "sex"],
    "address": ["address"],
    "aadhaar": ["aadhaar number (masked)", "aadhaar number", "aadhaar no", "aadhaar", "uid"],
    "generated": ["generated on", "download date"],
}


@register
class PanCardParser(DocumentParser):
    doc_type = "pan_card"

    def parse(self, pages: list[PageText]) -> ParseResult:
        res = ParseResult(self.doc_type)
        lines = all_lines(pages)
        meta = scan_labels(lines, PAN_META)
        m = PAN_RE.search(full_text(pages).upper())
        if m:
            chk = validate_pan(m.group(1))
            res.data.update({"pan": chk.pan, "pan_valid_format": chk.valid_format,
                             "pan_holder_type": chk.holder_type, "pan_surname_initial": chk.surname_initial})
            res.add("pan", chk.pan, line=meta.get("pan", (None, None))[1], confidence=0.9)
        else:
            candidates = meta.get("pan", ("", None))[0].split() + full_text(pages).split()
            repaired = next((r for w in candidates if (r := repair_pan(w))), None)
            if repaired:
                chk = validate_pan(repaired)
                res.data.update({"pan": chk.pan, "pan_valid_format": chk.valid_format, "pan_holder_type": chk.holder_type,
                                 "pan_surname_initial": chk.surname_initial, "pan_ocr_repaired": True})
                res.add("pan", repaired, line=meta.get("pan", (None, None))[1], confidence=0.7)
                res.warnings.append("PAN recovered with OCR character correction (O/0, I/1, S/5, B/8); verify against the document")
            else:
                res.warnings.append("No PAN pattern found")
        for key in ("name", "father_name"):
            if key in meta and meta[key][0]:
                res.data[key] = meta[key][0]
                res.add(key, meta[key][0], line=meta[key][1])
        if "dob" in meta:
            d = find_date(meta["dob"][0])
            if d:
                res.data["dob"] = d.isoformat()
                res.add("dob", meta["dob"][0], d.isoformat(), line=meta["dob"][1])
        return res


@register
class AadhaarParser(DocumentParser):
    doc_type = "aadhaar"

    def parse(self, pages: list[PageText]) -> ParseResult:
        res = ParseResult(self.doc_type)
        lines = all_lines(pages)
        text = full_text(pages)
        meta = scan_labels(lines, AADHAAR_META)
        full = AADHAAR_FULL_RE.search(text)
        masked = AADHAAR_MASKED_RE.search(text)
        if full:
            digits = "".join(full.groups())
            chk = validate_aadhaar(digits)
            # The full number is never stored: masked display + keyed match token only.
            res.data.update({"aadhaar_masked": chk.masked, "aadhaar_valid_format": chk.valid_format,
                             "aadhaar_checksum_valid": chk.checksum_valid, "aadhaar_issues": chk.issues,
                             "aadhaar_token": aadhaar_token(digits, settings.aadhaar_hmac_key)})
            res.add("aadhaar_masked", chk.masked, confidence=0.9)
        elif masked:
            res.data.update({"aadhaar_masked": f"XXXX XXXX {masked.group(3)}", "aadhaar_valid_format": None,
                             "aadhaar_checksum_valid": None, "aadhaar_issues": ["Number is masked; checksum not computable"]})
            res.add("aadhaar_masked", res.data["aadhaar_masked"], line=meta.get("aadhaar", (None, None))[1], confidence=0.9)
        else:
            res.warnings.append("No Aadhaar number pattern found")
        for key in ("name", "gender", "address"):
            if key in meta and meta[key][0]:
                res.data[key] = meta[key][0]
                res.add(key, meta[key][0], line=meta[key][1])
        if "dob" in meta:
            d = find_date(meta["dob"][0])
            if d:
                res.data["dob"] = d.isoformat()
                res.add("dob", meta["dob"][0], d.isoformat(), line=meta["dob"][1])
            elif re.fullmatch(r"\d{4}", meta["dob"][0].strip()):
                res.data["yob"] = meta["dob"][0].strip()
                res.add("yob", res.data["yob"], line=meta["dob"][1])
        if "name" not in res.data:  # physical cards print the name without a label, often over two lines
            cands = [ln for ln in lines if re.fullmatch(r"(?:[A-Z][a-z]+\.?\s*){2,6}", ln.text.strip())
                     and not re.search(r"government|india|aadhaar|male|female|unique|identification|authority", ln.text, re.I)]
            if cands:
                res.data["name"] = " ".join(c.text.strip() for c in cands[:2])
                res.add("name", res.data["name"], line=cands[0], confidence=0.6)
                res.warnings.append("Name taken from unlabelled lines; verify against the document")
        if "gender" not in res.data:
            g = re.search(r"\b(MALE|FEMALE|TRANSGENDER)\b", text, re.I)
            if g:
                res.data["gender"] = g.group(1).title()
                res.add("gender", res.data["gender"], confidence=0.7)
        return res