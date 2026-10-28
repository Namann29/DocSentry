from collections.abc import Generator, Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=True,
)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _record):  # type: ignore[no-untyped-def]
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def transaction(db: Session) -> Iterator[Session]:
    """Context manager: commit on success, roll back on any exception."""
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise


_SQLITE_TRIGGERS = [
    "CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_events "
    "BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;",
    "CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_events "
    "BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;",
]

_PG_TRIGGERS = [
    "CREATE OR REPLACE FUNCTION audit_block() RETURNS trigger AS $$ "
    "BEGIN RAISE EXCEPTION 'audit log is append-only'; END; $$ LANGUAGE plpgsql;",
    "DROP TRIGGER IF EXISTS audit_no_update ON audit_events;",
    "CREATE TRIGGER audit_no_update BEFORE UPDATE OR DELETE ON audit_events "
    "FOR EACH ROW EXECUTE FUNCTION audit_block();",
]


def ensure_audit_triggers() -> None:
    """Idempotent: safe to run after create_all or after Alembic migrations."""
    stmts = _SQLITE_TRIGGERS if _is_sqlite else _PG_TRIGGERS
    with engine.begin() as conn:
        for s in stmts:
            conn.execute(text(s))