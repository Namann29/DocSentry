import hashlib
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import settings
from .errors import AuthError


def _prehash(password: str) -> bytes:
    # bcrypt silently truncates at 72 bytes; SHA-256 first removes the limit.
    return hashlib.sha256(password.encode("utf-8")).hexdigest().encode("ascii")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, stored: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(password), stored.encode("ascii"))
    except ValueError:
        return False


def create_token(user_id: int, role: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": str(user_id), "role": role, "exp": exp}, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as e:
        raise AuthError("Token expired") from e
    except jwt.InvalidTokenError as e:
        raise AuthError("Invalid token") from e