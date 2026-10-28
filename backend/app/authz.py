from enum import StrEnum

from .errors import ForbiddenError
from .models import Case, User


class Role(StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


# action -> roles allowed regardless of ownership
_GLOBAL = {
    "case:read": {Role.ADMIN, Role.REVIEWER},
    "case:write": {Role.ADMIN},
    "case:delete": {Role.ADMIN},
    "case:review": {Role.ADMIN, Role.REVIEWER},
    "case:create": {Role.ADMIN, Role.ANALYST},
    "user:manage": {Role.ADMIN},
    "audit:read": {Role.ADMIN, Role.REVIEWER},
}
# action -> roles allowed on cases they own
_OWNER = {
    "case:read": {Role.ANALYST, Role.VIEWER},
    "case:write": {Role.ANALYST},
    "case:delete": {Role.ANALYST},
}


def authorize(user: User, action: str, case: Case | None = None) -> None:
    """Single authorization choke point. Raise ForbiddenError unless allowed."""
    role = Role(user.role)
    if role in _GLOBAL.get(action, set()):
        return
    if case is not None and case.owner_id == user.id and role in _OWNER.get(action, set()):
        return
    raise ForbiddenError(f"Role '{role}' may not perform '{action}'")