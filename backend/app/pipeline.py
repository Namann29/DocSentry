"""Upload -> Extract -> Normalize -> Validate -> Compare -> Investigate -> Score. Shared by uploads, demo data and quick scans."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from . import audit
from .engines import DocView, run_engines
from .errors import ProcessingError
from .extraction.service import run_extraction
from .models import Case, Document, ExtractedField, Finding, Job
from .risk import assess, points_for
from .security_scan import scan_document
from .storage import get_storage

_PATH = re.compile(r"^(\w+)\[([^\]]+)\](?:\.(\w+))?$")
_PREFIX = {"txn": "transactions", "item": "items", "earning": "earnings", "deduction": "deductions"}


def set_path(data: dict[str, Any], name: str, value: str) -> None:
    m = _PATH.match(name)
    if not m:
        data[name] = value
        return
    coll, key, attr = m.groups()
    target = data.get(_PREFIX.get(coll, coll))
    if isinstance(target, list) and key.isdigit() and int(key) < len(target) and attr:
        target[int(key)][attr] = value
    elif isinstance(target, dict):
        target[key] = value


def extract_document(db: Session, doc: Document, expected_type: str | None = None) -> None:
    doc.status, doc.error_message = "processing", ""
    try:
        with get_storage().local_path(doc.stored_name) as path:
            out = run_extraction(path, expected_type=expected_type)
            scan = scan_document(path, out.pages, list(doc.security_flags or []), doc.pdf_metadata or {}, doc.sha256, doc.size_bytes, doc.content_type)
    except ProcessingError as e:
        doc.status, doc.error_message = "failed", e.message
        return
    doc.extraction_method = out.method
    if out.method == "needs_ocr":
        doc.status, doc.doc_type = "failed", "unknown"
        doc.error_message = ("No text layer found and OCR is not available (install Tesseract to enable it), "
                             "so scanned or photographed documents cannot be extracted yet.")
        doc.parsed = {"_security": scan, "_warnings": [doc.error_message]}
        flag_modified(doc, "parsed")
        return
    doc.doc_type, doc.classification_confidence = out.classification.doc_type, out.classification.confidence
    corrected = {f.name: f for f in doc.fields if f.corrected}
    for f in list(doc.fields):
        if not f.corrected:
            db.delete(f)
    db.flush()
    data = dict(out.result.data) if out.result else {}
    for fd in (out.result.fields if out.result else []):
        if fd.name in corrected:
            set_path(data, fd.name, corrected[fd.name].normalized_value)
            continue
        db.add(ExtractedField(document_id=doc.id, name=fd.name, value=fd.value, normalized_value=fd.normalized,
                              confidence=fd.confidence, page=fd.page, bbox=fd.bbox, snippet=fd.snippet, method=fd.method))
    data["_warnings"] = out.result.warnings if out.result else []
    data["_classification_scores"] = out.classification.scores
    data["_security"] = scan
    data["_ocr_quality"] = [dict(page=p.number, **p.quality) for p in out.pages if p.quality]
    doc.parsed = data
    flag_modified(doc, "parsed")
    if out.result:
        doc.status = "processed"
    else:
        doc.status, doc.error_message = "unsupported", "Document type could not be determined; no parser was applied"


def _progress(db: Session, job: Job | None, pct: int, msg: str) -> None:
    if job:
        job.progress, job.message = pct, msg
        db.flush()


def process_case(db: Session, case: Case, actor_id: int, job: Job | None = None, force: bool = False,
                 engines: set[str] | None = None) -> dict[str, Any]:
    docs = [d for d in case.documents if d.deleted_at is None]
    for i, d in enumerate(docs):
        if force or d.status in ("uploaded", "failed", "unsupported"):
            extract_document(db, d)
        _progress(db, job, 10 + int(60 * (i + 1) / max(len(docs), 1)), f"Extracted {d.original_filename}")
    db.flush()
    def _rule_type(d: Document) -> str:
        weak = (d.parsed or {}).get("_classification_scores", {}).get("_weak_parse")
        return "unknown" if weak else d.doc_type

    views = [DocView(d.id, _rule_type(d), d.original_filename, d.parsed or {}, {f.name: f.confidence for f in d.fields})
             for d in docs if d.status == "processed"]
    findings, checks = run_engines(views, engines)
    _progress(db, job, 85, f"{len(findings)} findings from {len(checks)} checks")
    for f in list(case.findings):
        db.delete(f)
    db.flush()
    for f in findings:
        db.add(Finding(case_id=case.id, engine=f.engine, rule_id=f.rule_id, level=f.level, severity=f.severity, title=f.title[:200],
                       explanation=f.explanation, evidence=f.evidence, points=points_for(f), possible_extraction_error=f.possible_extraction_error))
    failed = [d for d in docs if d.status != "processed"]
    risk = assess(findings, checks, views, len(failed))
    case.risk_score, case.risk_outcome, case.risk_breakdown = risk.score, risk.outcome, risk.breakdown
    case.evidence_coverage, case.extraction_quality = risk.coverage, risk.extraction_quality
    case.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    flag_modified(case, "risk_breakdown")
    audit.record(db, actor_id, "case.process", "case", case.id,
                 {"documents": len(docs), "processed": len(views), "failed": len(failed), "findings": len(findings),
                  "outcome": risk.outcome, "score": risk.score, "engines": sorted(engines) if engines else "all"})
    _progress(db, job, 100, "Completed")
    return {"documents": len(docs), "processed": len(views), "failed": [d.original_filename for d in failed],
            "findings": len(findings), "risk_score": risk.score, "risk_outcome": risk.outcome, "evidence_coverage": risk.coverage}