"""One entry point for every document that enters a case: uploads and demo scenarios alike."""
from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit
from .models import Case, Document
from .storage import get_storage
from .upload import inspect_pdf, validate_upload


def ingest_file(db: Session, case: Case, filename: str, data: bytes, actor_id: int,
                password: str | None = None) -> Document:
    safe, ctype = validate_upload(filename, data)
    sha = hashlib.sha256(data).hexdigest()
    flags: list[str] = []
    meta, page_count, stored = None, 1, data
    if ctype == "application/pdf":
        insp = inspect_pdf(data, password)
        stored, page_count, flags, meta = insp.data, insp.page_count, list(insp.flags), insp.metadata
        if insp.decrypted:
            flags.append("decrypted_at_upload")
    dup = db.execute(select(Document.id).where(Document.case_id == case.id, Document.sha256 == sha,
                                               Document.deleted_at.is_(None))).first()
    if dup:
        flags.append(f"exact_duplicate_of_document_{dup[0]}")
    name = get_storage().save(stored, Path(safe).suffix.lower())
    doc = Document(case_id=case.id, original_filename=safe, stored_name=name, content_type=ctype,
                   size_bytes=len(data), sha256=sha, page_count=page_count, security_flags=flags, pdf_metadata=meta)
    db.add(doc)
    db.flush()
    audit.record(db, actor_id, "document.upload", "document", doc.id,
                 {"case_id": case.id, "sha256": sha, "size": len(data), "flags": flags})
    return doc