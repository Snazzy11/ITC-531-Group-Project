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


def unauthenticated(detail: str) -> APIError:
    """401 means we don't know who you are. A 401 has to say how to log in, hence the header."""
    return APIError(401, errors.UNAUTHENTICATED, detail, headers={"WWW-Authenticate": "Bearer"})


def current_user(
    token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    if not token:
        raise unauthenticated("not authenticated")
    try:
        user_id = int(read_access_token(token).get("sub", ""))
    except (TokenError, ValueError):
        raise unauthenticated("invalid token") from None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthenticated("unknown or inactive user")
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
"""For routes that only need someone signed in: `dependencies=[login_required]`."""

admin = Depends(require_role("admin"))
"""For admin-only routes: `dependencies=[admin]`."""


def is_admin(user: User) -> bool:
    return any(r.name == "admin" for r in user.roles)


def require_owner_or_admin(user: User, owner_id: int) -> None:
    """403 unless `user` owns the row or is an admin. Call it after loading the row."""
    if user.id != owner_id and not is_admin(user):
        raise APIError(403, errors.FORBIDDEN, "you do not own this resource")
