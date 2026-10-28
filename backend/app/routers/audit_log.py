from fastapi import APIRouter
from sqlalchemy import select

from .. import audit
from ..authz import authorize
from ..deps import DB, CurrentUser
from ..models import AuditEvent
from ..schemas import AuditEventOut

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events", response_model=list[AuditEventOut])
def events(db: DB, user: CurrentUser, limit: int = 200) -> list[AuditEvent]:
    authorize(user, "audit:read")
    return list(db.execute(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)).scalars())


@router.get("/verify")
def verify(db: DB, user: CurrentUser) -> dict:
    authorize(user, "audit:read")
    r = audit.verify_chain(db)
    return {"ok": r.ok, "checked": r.checked, "first_bad_id": r.first_bad_id, "head_hash": r.head_hash,
            "note": "Tamper-evident hash chain, not a blockchain. A database superuser could rewrite it; "
                    "AWS mode will witness the head hash in CloudWatch."}