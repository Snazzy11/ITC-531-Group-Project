import crud
import errors
import schemas
from auth import admin, current_user, require_owner_or_admin
from database.database import get_db
from database.models import User
from errors import APIError
from fastapi import APIRouter, Depends, Query
from password_util import PasswordTooLongError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

router = APIRouter(tags=["users"])


@router.post(  # TODO: Needs actual testing
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
    offset: int = Query(default=0, ge=0),
):
    return crud.list_users(db, limit=limit, offset=offset)


@router.patch(
    "/users/{user_id}",
    response_model=schemas.UserResponse,
    responses=errors.errors(401, 403, 404, 409, 422),
)
def update_user(
    user_id: int,
    changes: schemas.UserUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Change a display name or real name: your own, or anyone's as an admin."""
    target = crud.get_user(db, user_id)
    if target is None:
        raise APIError(404, errors.USER_NOT_FOUND, "user not found")
    require_owner_or_admin(user, target.id)
    payload = changes.model_dump(exclude_unset=True)
    if not payload:
        raise APIError(
            422, errors.EMPTY_UPDATE, "the request must change at least one field"
        )
    try:
        return crud.update_user(db, target, payload)
    except IntegrityError:
        db.rollback()
        raise APIError(
            409, errors.USER_NAME_TAKEN, "a user with that display name already exists"
        ) from None
