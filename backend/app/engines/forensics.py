from __future__ import annotations

from .base import Context, FindingDTO, ev, rule

SEV_BY_POINTS = ((30, "high"), (15, "medium"), (5, "low"), (0, "info"))


@rule("forensics", description="PDF structure, metadata and font-consistency indicators (heuristic, potential anomalies only)")
def document_security(ctx: Context) -> list[FindingDTO]:
    out: list[FindingDTO] = []
    for d in ctx.docs:
        s = d.get("_security")
        if not s:
            continue
        for c in s.get("contributions", []):
            if c["category"] == "sensitive":
                sev = "low" if c["check"] == "aadhaar_exposure" else "info"
            else:
                sev = next(label for floor, label in SEV_BY_POINTS if c["points"] >= floor)
            out.append(FindingDTO("forensics", "forensics.document_security", 6, sev, f"{d.filename}: {c['title']}", c["explanation"],
                                  [ev(d, c.get("field", c["check"]), c.get("value"), c.get("page"), bbox=c.get("bbox"))]))
        if not any(c["category"] in ("structure", "modification", "metadata") and c["points"] for c in s.get("contributions", [])):
            out.append(FindingDTO("forensics", "forensics.document_security", 6, "info", f"{d.filename}: no structural or modification indicators",
                                  "Single save, consistent fonts for numeric values, consistent metadata. This does not establish authenticity.", [ev(d, "security_score", s.get("score"))]))
    return out