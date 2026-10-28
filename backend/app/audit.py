import hashlib
import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AuditEvent

GENESIS = "0" * 64
_lock = threading.Lock()  # process-level serialisation; Postgres advisory lock is a later addition


def _digest(prev_hash: str, actor_id: int | None, action: str, resource_type: str,
            resource_id: str, detail: dict[str, Any], created_at: str) -> str:
    payload = json.dumps(
        [prev_hash, actor_id, action, resource_type, resource_id, detail, created_at],
        sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def record(db: Session, actor_id: int | None, action: str, resource_type: str,
           resource_id: int | str, detail: dict[str, Any] | None = None) -> AuditEvent:
    """Append one event. `detail` must contain no raw PII (callers mask first)."""
    detail = detail or {}
    with _lock:
        last = db.execute(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1)).scalar_one_or_none()
        prev = last.hash if last else GENESIS
        ts = datetime.now(timezone.utc).isoformat()
        ev = AuditEvent(
            prev_hash=prev, actor_id=actor_id, action=action, resource_type=resource_type,
            resource_id=str(resource_id), detail=detail, created_at=ts,
            hash=_digest(prev, actor_id, action, resource_type, str(resource_id), detail, ts),
        )
        db.add(ev)
        db.flush()
        return ev


@dataclass(frozen=True)
class ChainReport:
    ok: bool
    checked: int
    first_bad_id: int | None
    head_hash: str


def verify_chain(db: Session) -> ChainReport:
    prev = GENESIS
    checked = 0
    for ev in db.execute(select(AuditEvent).order_by(AuditEvent.id)).scalars():
        expected = _digest(prev, ev.actor_id, ev.action, ev.resource_type, ev.resource_id, ev.detail, ev.created_at)
        if ev.prev_hash != prev or ev.hash != expected:
            return ChainReport(False, checked, ev.id, prev)
        prev = ev.hash
        checked += 1
    return ChainReport(True, checked, None, prev)