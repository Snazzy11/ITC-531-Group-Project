"""Authentication dependencies, shared by api.py and the routers.

They live in their own module so a router can import them without importing
api.py (which imports every router).
"""
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

import errors
from database.database import get_db
from database.models import User
from errors import APIError
from tokens import TokenError, read_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


def current_user(
    token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    if not token:
        raise APIError(401, errors.UNAUTHENTICATED, "not authenticated")
    try:
        user_id = int(read_access_token(token).get("sub", ""))
    except (TokenError, ValueError):
        raise APIError(401, errors.UNAUTHENTICATED, "invalid token") from None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise APIError(401, errors.UNAUTHENTICATED, "unknown or inactive user")
    return user


def require_role(*allowed: str):
    def dependency(user: User = Depends(current_user)) -> User:
        if not {r.name for r in user.roles}.intersection(allowed):
            raise APIError(
                403, errors.FORBIDDEN, f"requires one of: {', '.join(sorted(allowed))}"
            )
        return user

    return dependency


login_required = Depends(current_user)
"""Use as `dependencies=[login_required]` when the route only needs to know
someone is signed in, not who."""

admin = Depends(require_role("admin"))
"""Use as `dependencies=[admin]` on a route that only admins may call."""


def is_admin(user: User) -> bool:
    return any(r.name == "admin" for r in user.roles)


def require_owner_or_admin(user: User, owner_id: int) -> None:
    """Call inside a route once the row is loaded: 403 unless `user` owns it
    or is an admin."""
    if user.id != owner_id and not is_admin(user):
        raise APIError(403, errors.FORBIDDEN, "you do not own this resource")
