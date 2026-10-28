import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from app import audit
from app.db import SessionLocal, ensure_audit_triggers


def test_chain_verifies_after_activity(client, users):
    r = client.get("/api/audit/verify", headers=users["admin"])
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["checked"] > 0


def test_tampering_is_detected_or_blocked(client, users):
    with SessionLocal() as db:
        # 1. The database itself refuses updates/deletes (append-only trigger).
        with pytest.raises(DatabaseError):
            db.execute(text("UPDATE audit_events SET action='forged' WHERE id=1"))
            db.commit()
        db.rollback()
        with pytest.raises(DatabaseError):
            db.execute(text("DELETE FROM audit_events WHERE id=1"))
            db.commit()
        db.rollback()
        # 2. Even if the trigger were bypassed, verification would catch a broken link.
        original = db.execute(text("SELECT action FROM audit_events WHERE id=1")).scalar_one()
        db.execute(text("DROP TRIGGER audit_no_update"))
        db.execute(text("UPDATE audit_events SET action='forged' WHERE id=1"))
        db.commit()
        report = audit.verify_chain(db)
        assert report.ok is False and report.first_bad_id == 1
        db.execute(text("UPDATE audit_events SET action=:a WHERE id=1"), {"a": original})
        db.commit()
    ensure_audit_triggers()
    with SessionLocal() as db:
        assert audit.verify_chain(db).ok is True


def test_viewer_cannot_read_audit(client, users):
    assert client.get("/api/audit/events", headers=users["viewer"]).status_code == 403