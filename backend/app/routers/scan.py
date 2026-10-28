from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, UploadFile
from sqlalchemy.orm.attributes import flag_modified

from .. import audit
from ..authz import authorize
from ..db import transaction
from ..deps import DB, CurrentUser
from ..extraction.service import get_adapter
from ..ingest import ingest_file
from ..models import Case
from ..pipeline import extract_document, process_case
from ..security_scan import scan_document
from ..storage import get_storage
from .documents import load_document

router = APIRouter(tags=["security"])


@router.get("/documents/{doc_id}/security")
def document_security(doc_id: int, db: DB, user: CurrentUser, force: bool = False) -> dict:
    doc = load_document(db, doc_id, user, "case:read")
    scan = None if force else (doc.parsed or {}).get("_security")
    if scan is None:
        with get_storage().local_path(doc.stored_name) as path:
            pages = list(get_adapter().extract(path))
            scan = scan_document(path, pages, list(doc.security_flags or []), doc.pdf_metadata or {}, doc.sha256, doc.size_bytes, doc.content_type)
        parsed = dict(doc.parsed or {})
        parsed["_security"] = scan
        doc.parsed = parsed
        flag_modified(doc, "parsed")
        audit.record(db, user.id, "document.security_scan", "document", doc.id, {"score": scan["score"], "level": scan["level"]})
        db.commit()
    return scan


@router.post("/scan", status_code=201)
def quick_scan(db: DB, user: CurrentUser, file: UploadFile = File(...), password: str | None = Form(default=None), expected_type: str | None = Form(default=None)) -> dict:
    """One file -> its own case: ingested, extracted (OCR if needed), scanned and fully analysed."""
    authorize(user, "case:create")
    with transaction(db):
        case = Case(title=f"Quick scan {datetime.now(timezone.utc):%Y-%m-%d %H:%M}", case_type="scan", owner_id=user.id,
                    description="Single-document security scan")
        db.add(case)
        db.flush()
        doc = ingest_file(db, case, file.filename or "upload", file.file.read(), user.id, password or None)
        extract_document(db, doc, expected_type or None)
        process_case(db, case, user.id)
        audit.record(db, user.id, "document.security_scan", "document", doc.id,
                     {"score": (doc.parsed or {}).get("_security", {}).get("score"), "quick": True})
    parsed = doc.parsed or {}
    return {"case_id": case.id, "document_id": doc.id, "filename": doc.original_filename, "doc_type": doc.doc_type,
            "status": doc.status, "error_message": doc.error_message, "page_count": doc.page_count,
            "extraction_method": doc.extraction_method, "scan": parsed.get("_security"), "ocr_quality": parsed.get("_ocr_quality"), "classification_confidence": doc.classification_confidence, "weak_parse": bool(parsed.get("_classification_scores", {}).get("_weak_parse")), "warnings": parsed.get("_warnings", []), "expected_type": expected_type or None, "type_assumed": bool(parsed.get("_classification_scores", {}).get("_assumed_from_user")), "type_mismatch": bool(parsed.get("_classification_scores", {}).get("_expected_type_mismatch")),
            "fields": {k: v for k, v in parsed.items() if not k.startswith("_") and not isinstance(v, (list, dict))}}