from datetime import datetime, timezone

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..authz import Role, authorize
from ..db import transaction
from ..deps import DB, CurrentUser
from ..errors import NotFoundError
from ..models import Case, Document, Finding, User
from ..schemas import CaseCreate, CaseOut, CaseUpdate

router = APIRouter(prefix="/cases", tags=["cases"])


def load_case(db: Session, case_id: int, user: User, action: str) -> Case:
    """Every case-scoped endpoint goes through here: load, 404, then authorize."""
    case = db.get(Case, case_id)
    if case is None or case.deleted_at is not None:
        raise NotFoundError("Case not found")
    authorize(user, action, case)
    return case


def _to_out(db: Session, case: Case) -> CaseOut:
    out = CaseOut.model_validate(case)
    out.document_count = db.scalar(select(func.count(Document.id)).where(
        Document.case_id == case.id, Document.deleted_at.is_(None))) or 0
    out.finding_count = db.scalar(select(func.count(Finding.id)).where(Finding.case_id == case.id)) or 0
    return out


@router.get("", response_model=list[CaseOut])
def list_cases(db: DB, user: CurrentUser, q: str | None = None,
               status: str | None = Query(default=None)) -> list[CaseOut]:
    stmt = select(Case).where(Case.deleted_at.is_(None)).order_by(Case.updated_at.desc())
    if Role(user.role) not in (Role.ADMIN, Role.REVIEWER):
        stmt = stmt.where(Case.owner_id == user.id)
    if q:
        stmt = stmt.where(Case.title.ilike(f"%{q}%"))
    if status:
        stmt = stmt.where(Case.status == status)
    return [_to_out(db, c) for c in db.execute(stmt).scalars()]


@router.post("", response_model=CaseOut, status_code=201)
def create_case(body: CaseCreate, db: DB, user: CurrentUser) -> CaseOut:
    authorize(user, "case:create")
    with transaction(db):
        case = Case(title=body.title, case_type=body.case_type, description=body.description, owner_id=user.id)
        db.add(case)
        db.flush()
        audit.record(db, user.id, "case.create", "case", case.id, {"case_type": body.case_type})
    return _to_out(db, case)


@router.get("/{case_id}", response_model=CaseOut)
def get_case(case_id: int, db: DB, user: CurrentUser) -> CaseOut:
    case = load_case(db, case_id, user, "case:read")
    audit.record(db, user.id, "case.view", "case", case.id)
    db.commit()
    return _to_out(db, case)


@router.patch("/{case_id}", response_model=CaseOut)
def update_case(case_id: int, body: CaseUpdate, db: DB, user: CurrentUser) -> CaseOut:
    case = load_case(db, case_id, user, "case:write")
    with transaction(db):
        changed = body.model_dump(exclude_none=True)
        for k, v in changed.items():
            setattr(case, k, v)
        audit.record(db, user.id, "case.update", "case", case.id, {"fields": sorted(changed)})
    return _to_out(db, case)


@router.delete("/{case_id}", status_code=204)
def delete_case(case_id: int, db: DB, user: CurrentUser, reason: str = Query(min_length=3)) -> None:
    case = load_case(db, case_id, user, "case:delete")
    with transaction(db):
        case.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        audit.record(db, user.id, "case.soft_delete", "case", case.id, {"reason": reason})