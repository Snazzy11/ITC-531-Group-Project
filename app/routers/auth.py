from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

import errors
import schemas
from auth import current_user, require_role
from database.database import get_db
from database.models import User
from errors import APIError
from password_util import verify_password
from tokens import TOKEN_MINUTES, create_access_token

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=schemas.TokenOut, responses=errors.errors(401))
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Form fields `username` (the display name) and `password`. The token's
    `sub` is the user's id."""
    user = db.scalar(select(User).where(User.display_name == form.username))
    if user is None or not user.is_active or not verify_password(form.password, user.password_hash):
        raise APIError(401, errors.UNAUTHENTICATED, "incorrect display name or password")
    return schemas.TokenOut(
        access_token=create_access_token(str(user.id)), expires_in=TOKEN_MINUTES * 60
    )


@router.get("/auth/me", response_model=schemas.UserResponse, responses=errors.errors(401))
def me(user: User = Depends(current_user)):
    return user


@router.get(
    "/admin/users",
    response_model=list[schemas.UserResponse],
    responses=errors.errors(401, 403),
)
def admin_list_users(_: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    return list(db.scalars(select(User).order_by(User.id)))
