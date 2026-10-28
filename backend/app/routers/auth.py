from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import select

from .. import audit
from ..authz import authorize
from ..config import settings
from ..db import transaction
from ..deps import DB, CurrentUser
from ..errors import AuthError, InvalidInputError, LockedError
from ..models import User
from ..schemas import LoginRequest, TokenResponse, UserCreate, UserOut
from ..security import create_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: DB) -> TokenResponse:
    user = db.execute(select(User).where(User.email == body.email.lower())).scalar_one_or_none()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if user and user.locked_until and user.locked_until > now:
        raise LockedError("Account temporarily locked after repeated failures")
    if user is None or not verify_password(body.password, user.password_hash):
        if user is not None:
            with transaction(db):
                user.failed_logins += 1
                if user.failed_logins >= settings.lockout_threshold:
                    user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
                    user.failed_logins = 0
                audit.record(db, user.id, "auth.login_failed", "user", user.id)
        raise AuthError("Invalid email or password")
    with transaction(db):
        user.failed_logins = 0
        user.locked_until = None
        audit.record(db, user.id, "auth.login", "user", user.id)
    return TokenResponse(access_token=create_token(user.id, user.role))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, db: DB, actor: CurrentUser) -> User:
    authorize(actor, "user:manage")  # roles are assigned by admins only, never self-selected
    if db.execute(select(User).where(User.email == body.email.lower())).scalar_one_or_none():
        raise InvalidInputError("Email already registered")
    with transaction(db):
        user = User(email=body.email.lower(), password_hash=hash_password(body.password), role=body.role)
        db.add(user)
        db.flush()
        audit.record(db, actor.id, "user.create", "user", user.id, {"role": body.role})
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(db: DB, actor: CurrentUser) -> list[User]:
    authorize(actor, "user:manage")
    return list(db.execute(select(User).order_by(User.id)).scalars())