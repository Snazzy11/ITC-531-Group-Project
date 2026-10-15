from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import presenters
import crud
import errors
import schemas
from database.database import get_db
from errors import APIError
from auth import admin

router = APIRouter(tags=["locations"])


@router.post(
    "/locations",
    response_model=schemas.LocationResponse,
    status_code=201,
    dependencies=[admin],
    responses=errors.errors(401, 403, 409, 422),
)
def create_location(location: schemas.LocationCreate, db: Session = Depends(get_db)):
    try:
        return crud.create_location(db, location)
    except IntegrityError:
        db.rollback()
        raise APIError(
            409, errors.LOCATION_NAME_TAKEN, "a location with that name already exists"
        ) from None


@router.get("/locations", response_model=list[schemas.LocationAdminResponse])
def list_locations(
    db: Session = Depends(get_db),
    include_inactive: bool = False,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Active locations only by default."""
    return crud.list_locations(
        db, include_inactive=include_inactive, limit=limit, offset=offset
    )


@router.get(
    "/locations/{location_id}",
    response_model=schemas.LocationResponse,
    responses=errors.errors(404),
)
def get_location(location_id: int, db: Session = Depends(get_db)):
    location = crud.get_location(db, location_id)
    if location is None:
        raise APIError(404, errors.LOCATION_NOT_FOUND, "location not found")
    return location


@router.get(
    "/locations/{location_id}/items",
    response_model=list[schemas.ItemResponse],
    responses=errors.errors(404),
)
def items_by_location(location_id: int, db: Session = Depends(get_db)):
    if crud.get_location(db, location_id) is None:
        raise APIError(404, errors.LOCATION_NOT_FOUND, "location not found")
    return [presenters.item_out(item) for item in crud.list_items(db, location_id=location_id)]


@router.patch(
    "/locations/{location_id}",
    response_model=schemas.LocationResponse,
    dependencies=[admin],
    responses=errors.errors(401, 403, 404, 409, 422),
)
def update_location(
    location_id: int, changes: schemas.LocationUpdate, db: Session = Depends(get_db)
):
    location = crud.get_location(db, location_id)
    if location is None:
        raise APIError(404, errors.LOCATION_NOT_FOUND, "location not found")
    payload = changes.model_dump(exclude_unset=True)
    if not payload:
        raise APIError(422, errors.EMPTY_UPDATE, "the request must change at least one field")
    try:
        return crud.update_location(db, location, payload)
    except IntegrityError:
        db.rollback()
        raise APIError(
            409, errors.LOCATION_NAME_TAKEN, "a location with that name already exists"
        ) from None


@router.delete(
    "/locations/{location_id}",
    status_code=204,
    dependencies=[admin],
    responses=errors.errors(401, 403, 404),
)
def retire_location(location_id: int, db: Session = Depends(get_db)):
    """Soft delete: sets is_active to false. Existing posts keep the location;
    new posts can no longer select it."""
    location = crud.get_location(db, location_id)
    if location is None:
        raise APIError(404, errors.LOCATION_NOT_FOUND, "location not found")
    crud.set_location_active(db, location, False)
    return Response(status_code=204)


@router.post(
    "/locations/{location_id}/restore",
    response_model=schemas.LocationAdminResponse,
    dependencies=[admin],
    responses=errors.errors(401, 403, 404),
)
def restore_location(location_id: int, db: Session = Depends(get_db)):
    location = crud.get_location(db, location_id)
    if location is None:
        raise APIError(404, errors.LOCATION_NOT_FOUND, "location not found")
    return crud.set_location_active(db, location, True)


@router.delete(
    "/locations/{location_id}/hard",
    status_code=204,
    dependencies=[admin],
    responses=errors.errors(401, 403, 404, 409),
)
def hard_delete_location(location_id: int, db: Session = Depends(get_db)):
    location = crud.get_location(db, location_id)
    if location is None:
        raise APIError(404, errors.LOCATION_NOT_FOUND, "location not found")
    in_use = crud.count_items_at_location(db, location_id)
    if in_use:
        raise APIError(
            409, errors.LOCATION_IN_USE, f"{in_use} post(s) use that location; retire it instead"
        )
    try:
        crud.delete_location(db, location)
    except IntegrityError:
        db.rollback()
        raise APIError(
            409, errors.LOCATION_IN_USE, "that location is still referenced by existing posts"
        ) from None
    return Response(status_code=204)
