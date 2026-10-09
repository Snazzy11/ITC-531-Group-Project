from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette import status

import crud
import errors
import schemas
from api import oauth2_scheme
from database.database import get_db
from database.models import User
from errors import APIError
from tokens import TokenError, read_access_token

router = APIRouter(tags=["users"])


@router.post( # TODO: Needs actual testing
    "/users",
    response_model=schemas.UserResponse,
    status_code=201,
    responses=errors.errors(409, 422),
)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    try:
        return crud.create_user(db, user)
    except IntegrityError:
        db.rollback()
        raise APIError(
            409, errors.USER_NAME_TAKEN, "a user with that display name already exists"
        ) from None

@router.get("/users", response_model=list[schemas.UserResponse])
def list_users(
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0)
):
    return crud.list_users(db, limit=limit, offset=offset)

def current_user(
    token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    try:
        payload = read_access_token(token)
    except TokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token") from None
    user = db.scalar(select(User).where(User.display_name == payload.get("sub"))) # TODO ensure this works as display name was swapped for email
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown or inactive user")
    return user