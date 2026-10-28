import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from . import models  # noqa: F401
from .config import settings
from .db import Base, SessionLocal, engine, ensure_audit_triggers
from .engines import RULES
from .errors import install_handlers
from .extraction.service import ocr_engine
from .models import User
from .routers import audit_log, auth, cases, demo, documents, processing, scan
from .security import hash_password

log = logging.getLogger("docsentry")


def init_db() -> None:
    if settings.auto_create_tables:
        Base.metadata.create_all(engine)
    ensure_audit_triggers()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        if db.execute(select(User).limit(1)).scalar_one_or_none() is None:
            db.add(User(email=settings.admin_email.lower(), password_hash=hash_password(settings.admin_password), role="admin"))
            db.commit()
            log.warning("Seeded initial admin user %s from settings", settings.admin_email)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if ocr_engine() in ("easyocr", "ensemble"):  # preload the OCR model so the first scan is not slow
        from .extraction.easyocr_adapter import reader
        threading.Thread(target=reader, daemon=True).start()
    yield


app = FastAPI(title="DocSentry API", version="0.6.1", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
install_handlers(app)
for r in (auth.router, cases.router, audit_log.router, documents.router, processing.router, demo.router, scan.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    eng = ocr_engine()
    return {"status": "ok", "run_mode": settings.run_mode, "version": app.version, "rules": len(RULES),
            "capabilities": {"native_pdf": True, "security_scan": True, "ocr": eng is not None, "ocr_engine": eng,
                             "textract": False, "bedrock": False, "s3": False, "compare": False, "rag": False}}


@app.get("/api/rules")
def rules() -> list[dict]:
    return [{"id": r.id, "engine": r.engine, "requires": list(r.requires), "description": r.description} for r in RULES.values()]