from fastapi import APIRouter, Depends, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import crud
import errors
import schemas
from database.database import get_db
from auth import admin
from errors import APIError
from password_util import PasswordTooLongError

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
    except PasswordTooLongError as exc:
        raise APIError(422, errors.VALIDATION_ERROR, str(exc)) from None
    except IntegrityError:
        db.rollback()
        raise APIError(
            409, errors.USER_NAME_TAKEN, "a user with that display name already exists"
        ) from None

@router.get(
    "/users",
    response_model=list[schemas.UserResponse],
    dependencies=[admin],
    responses=errors.errors(401, 403),
)
def list_users(
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0)
):
    return crud.list_users(db, limit=limit, offset=offset)
