"""PAN, Aadhaar (Verhoeff) and GSTIN structure/checksum checks.
These are FORMAT checks (taxonomy level 1). They never prove a document is genuine."""
from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass, field

PAN_RE = re.compile(r"(?<![A-Z0-9])([A-Z]{5}[0-9]{4}[A-Z])(?![A-Z0-9])")
PAN_MASKED_RE = re.compile(r"(?<![A-Z0-9])([A-Z]{5}[0-9X*]{4}[A-Z])(?![A-Z0-9])")
GSTIN_RE = re.compile(r"(?<![A-Z0-9])(\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z])(?![A-Z0-9])")
AADHAAR_FULL_RE = re.compile(r"(?<!\d)(\d{4})[\s-]?(\d{4})[\s-]?(\d{4})(?!\d)")
AADHAAR_MASKED_RE = re.compile(r"(?i)([x*]{4})[\s-]?([x*]{4})[\s-]?(\d{4})")
IFSC_RE = re.compile(r"(?<![A-Z0-9])([A-Z]{4}0[A-Z0-9]{6})(?![A-Z0-9])")

PAN_HOLDER_TYPES = {
    "P": "Individual", "C": "Company", "H": "HUF", "F": "Firm", "A": "AOP", "T": "Trust",
    "B": "BOI", "L": "Local authority", "J": "Artificial juridical person", "G": "Government",
}


@dataclass
class PanCheck:
    pan: str
    valid_format: bool
    holder_type: str | None = None
    surname_initial: str | None = None
    issues: list[str] = field(default_factory=list)


def validate_pan(pan: str) -> PanCheck:
    p = pan.strip().upper()
    if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", p):
        return PanCheck(p, False, issues=["PAN must be 5 letters, 4 digits, 1 letter"])
    holder = PAN_HOLDER_TYPES.get(p[3])
    issues = [] if holder else [f"Unknown holder-type code '{p[3]}' in 4th position"]
    return PanCheck(p, holder is not None, holder, p[4] if p[3] == "P" else None, issues)


# ---- Verhoeff -------------------------------------------------------------
_D = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
      [3, 4, 0, 1, 2, 8, 9, 5, 6, 7], [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
      [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3], [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
      [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]]
_P = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
      [8, 9, 1, 6, 0, 4, 3, 5, 2, 7], [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
      [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]]
_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def verhoeff_valid(number: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(number)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0


def verhoeff_checksum(number_without_check: str) -> str:
    c = 0
    for i, ch in enumerate(reversed(number_without_check)):
        c = _D[c][_P[(i + 1) % 8][int(ch)]]
    return str(_INV[c])


@dataclass
class AadhaarCheck:
    masked: str
    valid_format: bool
    checksum_valid: bool | None
    issues: list[str] = field(default_factory=list)


def mask_aadhaar(digits: str) -> str:
    return f"XXXX XXXX {digits[-4:]}"


def aadhaar_token(digits: str, key: str) -> str:
    """Keyed HMAC so two documents can be matched without storing the number."""
    return hmac.new(key.encode(), digits.encode(), hashlib.sha256).hexdigest()


def validate_aadhaar(digits: str) -> AadhaarCheck:
    d = re.sub(r"\D", "", digits)
    if len(d) != 12:
        return AadhaarCheck(mask_aadhaar(d.rjust(4, "0")), False, None, ["Aadhaar must have 12 digits"])
    issues = []
    if d[0] in "01":
        issues.append("First digit must be 2-9")
    ok = verhoeff_valid(d)
    if not ok:
        issues.append("Verhoeff checksum failed")
    return AadhaarCheck(mask_aadhaar(d), not issues, ok, issues)


# ---- GSTIN ---------------------------------------------------------------
_B36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin_checksum(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14.upper()):
        v = _B36.index(ch)
        prod = v * (2 if i % 2 else 1)
        total += prod // 36 + prod % 36
    return _B36[(36 - total % 36) % 36]


@dataclass
class GstinCheck:
    gstin: str
    valid_format: bool
    checksum_valid: bool
    state_code: str | None
    embedded_pan: str | None
    issues: list[str] = field(default_factory=list)


def validate_gstin(g: str) -> GstinCheck:
    g = g.strip().upper()
    if not re.fullmatch(r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]", g):
        return GstinCheck(g, False, False, None, None, ["GSTIN structure invalid"])
    ok = gstin_checksum(g[:14]) == g[14]
    return GstinCheck(g, True, ok, g[:2], g[2:12], [] if ok else ["GSTIN check digit mismatch"])

# ---- OCR repair -----------------------------------------------------------
_D2L = {"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z", "6": "G"}
_L2D = {"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "S": "5", "B": "8", "Z": "2", "G": "6"}


def repair_pan(token: str) -> str | None:
    """Position-aware correction of common OCR confusions in a PAN-shaped token.
    Letters are required in positions 1-5 and 10, digits in 6-9. Returns None if it still does not fit."""
    t = re.sub(r"[^A-Za-z0-9]", "", token).upper()
    if len(t) != 10:
        return None
    out = "".join((_D2L.get(ch, ch) if i < 5 or i == 9 else _L2D.get(ch, ch)) for i, ch in enumerate(t))
    return out if re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", out) else None
