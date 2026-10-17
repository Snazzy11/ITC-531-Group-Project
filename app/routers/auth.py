from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

import errors
import schemas
from auth import current_user, unauthenticated
from database.database import get_db
from database.models import User
from errors import APIError
from password_util import DUMMY_HASH, verify_password
from tokens import TOKEN_MINUTES, create_access_token

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=schemas.TokenOut, responses=errors.errors(401))
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Form fields `username` (the display name) and `password`. The token's
    `sub` is the user's id."""
    user = db.scalar(select(User).where(User.display_name == form.username))
    # The same message for no such user, inative account, or incorrect password
    # bcrypt will also always run, using the dummy hash when there is no
    # real user.
    usable = user is not None and user.is_active
    password_ok = verify_password(form.password, user.password_hash if usable else DUMMY_HASH)
    if not (usable and password_ok):
        raise unauthenticated("incorrect display name or password")
    return schemas.TokenOut(
        access_token=create_access_token(str(user.id)), expires_in=TOKEN_MINUTES * 60
    )


@router.get("/auth/me", response_model=schemas.UserResponse, responses=errors.errors(401))
def me(user: User = Depends(current_user)):
    return user
