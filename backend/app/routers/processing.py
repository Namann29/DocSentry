from datetime import datetime, timezone
from statistics import mean

from fastapi import APIRouter, Query, Response
from sqlalchemy import select

from .. import audit
from ..authz import authorize
from ..db import transaction
from ..deps import DB, CurrentUser
from ..errors import ProcessingError
from ..models import AuditEvent, Finding, Job
from ..pipeline import process_case
from ..report import build_report
from ..schemas import ExtractionStats, FindingOut, JobOut, ProcessOut, ReviewRequest, RiskOut
from .cases import load_case

router = APIRouter(tags=["processing"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.post("/cases/{case_id}/process", response_model=ProcessOut)
def process(case_id: int, db: DB, user: CurrentUser, force: bool = False,
            engines: str | None = Query(default=None, description="comma list for ablation, e.g. identity,financial")) -> ProcessOut:
    case = load_case(db, case_id, user, "case:write")
    job = Job(case_id=case.id, kind="process_case", status="processing", started_at=_now())
    db.add(job)
    db.flush()
    selected = {e.strip() for e in engines.split(",") if e.strip()} if engines else None
    try:
        summary = process_case(db, case, user.id, job, force, selected)
        job.status, job.finished_at = "completed", _now()
        db.commit()
    except Exception as e:  # noqa: BLE001
        db.rollback()
        failed = Job(case_id=case.id, kind="process_case", status="failed", message=f"{type(e).__name__}: {e}"[:500],
                     started_at=_now(), finished_at=_now())
        db.add(failed)
        db.commit()
        raise ProcessingError("Case processing failed; see job history") from e
    return ProcessOut(job_id=job.id, **summary)


@router.get("/cases/{case_id}/findings", response_model=list[FindingOut])
def findings(case_id: int, db: DB, user: CurrentUser, engine: str | None = None, severity: str | None = None,
             level: int | None = None) -> list[Finding]:
    case = load_case(db, case_id, user, "case:read")
    order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    out = [f for f in case.findings if (not engine or f.engine == engine) and (not severity or f.severity == severity) and (not level or f.level == level)]
    return sorted(out, key=lambda f: (order.get(f.severity, 9), f.rule_id))


@router.get("/cases/{case_id}/risk", response_model=RiskOut)
def risk(case_id: int, db: DB, user: CurrentUser) -> RiskOut:
    case = load_case(db, case_id, user, "case:read")
    return RiskOut(score=case.risk_score, outcome=case.risk_outcome, evidence_coverage=case.evidence_coverage,
                   extraction_quality=case.extraction_quality, breakdown=case.risk_breakdown or {})


@router.get("/cases/{case_id}/jobs", response_model=list[JobOut])
def jobs(case_id: int, db: DB, user: CurrentUser) -> list[Job]:
    load_case(db, case_id, user, "case:read")
    return list(db.execute(select(Job).where(Job.case_id == case_id).order_by(Job.id.desc())).scalars())


@router.get("/cases/{case_id}/extraction-stats", response_model=ExtractionStats)
def extraction_stats(case_id: int, db: DB, user: CurrentUser) -> ExtractionStats:
    case = load_case(db, case_id, user, "case:read")
    fields = [f for d in case.documents if d.deleted_at is None for f in d.fields]
    corrected = sum(1 for f in fields if f.corrected)
    return ExtractionStats(fields=len(fields), corrected=corrected, correction_rate=round(corrected / len(fields), 4) if fields else 0.0,
                           mean_confidence=round(mean(f.confidence for f in fields), 3) if fields else 0.0)


@router.post("/cases/{case_id}/review")
def review(case_id: int, body: ReviewRequest, db: DB, user: CurrentUser) -> dict:
    case = load_case(db, case_id, user, "case:review")
    with transaction(db):
        case.review_outcome, case.review_note, case.status = body.outcome, body.note, "reviewed"
        audit.record(db, user.id, "case.review", "case", case.id, {"outcome": body.outcome})
    return {"ok": True, "review_outcome": case.review_outcome}


@router.get("/cases/{case_id}/report.pdf")
def report(case_id: int, db: DB, user: CurrentUser) -> Response:
    case = load_case(db, case_id, user, "case:read")
    docs = [d for d in case.documents if d.deleted_at is None]
    events = list(db.execute(select(AuditEvent).where(AuditEvent.resource_type.in_(["case", "document"]))
                             .order_by(AuditEvent.id)).scalars())
    events = [e for e in events if (e.resource_type == "case" and e.resource_id == str(case.id))
              or (e.resource_type == "document" and e.resource_id in {str(d.id) for d in docs})]
    pdf = build_report(case, docs, list(case.findings), events)
    audit.record(db, user.id, "report.generate", "case", case.id, {"bytes": len(pdf)})
    db.commit()
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="docsentry_case_{case.id}.pdf"'})