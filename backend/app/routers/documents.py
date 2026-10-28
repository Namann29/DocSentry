from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, Query, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from .. import audit
from ..db import transaction
from ..deps import DB, CurrentUser
from ..errors import NotFoundError
from ..extraction.pymupdf_adapter import render_page_png
from ..ingest import ingest_file
from ..models import Document, ExtractedField, User
from ..pipeline import extract_document, set_path
from ..schemas import DocumentDetail, DocumentOut, FieldCorrection, FieldOut
from ..storage import get_storage
from .cases import load_case

router = APIRouter(tags=["documents"])


def load_document(db: Session, doc_id: int, user: User, action: str) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None or doc.deleted_at is not None:
        raise NotFoundError("Document not found")
    load_case(db, doc.case_id, user, action)  # authorization choke point
    return doc


@router.post("/cases/{case_id}/documents", response_model=list[DocumentOut], status_code=201)
def upload_documents(case_id: int, db: DB, user: CurrentUser, files: list[UploadFile] = File(...),
                     password: str | None = Form(default=None)) -> list[Document]:
    case = load_case(db, case_id, user, "case:write")
    docs = []
    with transaction(db):
        for f in files:
            docs.append(ingest_file(db, case, f.filename or "upload", f.file.read(), user.id, password or None))
    return docs


@router.get("/cases/{case_id}/documents", response_model=list[DocumentOut])
def list_documents(case_id: int, db: DB, user: CurrentUser) -> list[Document]:
    case = load_case(db, case_id, user, "case:read")
    return [d for d in case.documents if d.deleted_at is None]


@router.get("/documents/{doc_id}", response_model=DocumentDetail)
def get_document(doc_id: int, db: DB, user: CurrentUser) -> Document:
    doc = load_document(db, doc_id, user, "case:read")
    audit.record(db, user.id, "document.view", "document", doc.id)
    db.commit()
    return doc


@router.get("/documents/{doc_id}/pages/{page}")
def page_image(doc_id: int, page: int, db: DB, user: CurrentUser) -> Response:
    doc = load_document(db, doc_id, user, "case:read")
    with get_storage().local_path(doc.stored_name) as path:
        if doc.content_type == "application/pdf":
            png = render_page_png(path, page)
            return Response(content=png, media_type="image/png")
        return Response(content=path.read_bytes(), media_type=doc.content_type)


@router.get("/documents/{doc_id}/download")
def download(doc_id: int, db: DB, user: CurrentUser) -> Response:
    doc = load_document(db, doc_id, user, "case:read")
    data = get_storage().read(doc.stored_name)
    audit.record(db, user.id, "document.download", "document", doc.id, {"sha256": doc.sha256})
    db.commit()
    return Response(content=data, media_type=doc.content_type,
                    headers={"Content-Disposition": f'attachment; filename="{doc.original_filename}"'})


@router.post("/documents/{doc_id}/extract", response_model=DocumentDetail)
def extract_one(doc_id: int, db: DB, user: CurrentUser) -> Document:
    doc = load_document(db, doc_id, user, "case:write")
    with transaction(db):
        extract_document(db, doc)
        audit.record(db, user.id, "document.extract", "document", doc.id, {"status": doc.status, "doc_type": doc.doc_type})
    return doc


@router.get("/documents/{doc_id}/fields", response_model=list[FieldOut])
def list_fields(doc_id: int, db: DB, user: CurrentUser) -> list[ExtractedField]:
    doc = load_document(db, doc_id, user, "case:read")
    return sorted(doc.fields, key=lambda f: (f.page, f.name))


@router.patch("/documents/{doc_id}/fields/{field_id}", response_model=FieldOut)
def correct_field(doc_id: int, field_id: int, body: FieldCorrection, db: DB, user: CurrentUser) -> ExtractedField:
    doc = load_document(db, doc_id, user, "case:write")
    fld = db.get(ExtractedField, field_id)
    if fld is None or fld.document_id != doc.id:
        raise NotFoundError("Field not found")
    with transaction(db):
        if not fld.corrected:
            fld.original_value = fld.value
        fld.value, fld.normalized_value = body.value, body.normalized or body.value
        fld.corrected, fld.confidence, fld.method = True, 1.0, "manual"
        if doc.parsed is not None:
            set_path(doc.parsed, fld.name, fld.normalized_value)
            flag_modified(doc, "parsed")
        audit.record(db, user.id, "document.field_corrected", "document", doc.id, {"field": fld.name})
    return fld


@router.delete("/documents/{doc_id}", status_code=204)
def delete_document(doc_id: int, db: DB, user: CurrentUser, reason: str = Query(min_length=3)) -> None:
    doc = load_document(db, doc_id, user, "case:write")
    with transaction(db):
        doc.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        doc.delete_reason = reason
        audit.record(db, user.id, "document.soft_delete", "document", doc.id, {"reason": reason})