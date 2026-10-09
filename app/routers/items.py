import logging

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import crud
import errors
import messaging
import presenters
import schemas
from database import models
from database.database import get_db
from dependencies import admin
from errors import APIError
from ports import storage

log = logging.getLogger("lostfound")

router = APIRouter(tags=["items"])


@router.post(
    "/items",
    response_model=schemas.ItemResponse,
    status_code=201,
    responses=errors.errors(404, 409, 422),
)
def create_item(item: schemas.ItemCreate, db: Session = Depends(get_db)):
    if crud.get_user(db, item.user_id) is None:
        raise APIError(404, errors.USER_NOT_FOUND, "user not found")
    location = crud.get_location(db, item.location_id)
    if location is None:
        raise APIError(404, errors.LOCATION_NOT_FOUND, "location not found")
    if not location.is_active:
        raise APIError(
            409, errors.LOCATION_INACTIVE, "that location has been retired"
        )
    row = crud.create_item(db, item)
    messaging.emit("item.created", row.id)
    return presenters.item_out(row)


@router.get("/items", response_model=list[schemas.ItemResponse])
def list_items(
    db: Session = Depends(get_db),
    type: int | None = Query(default=None, ge=0, le=1, description="0 = lost, 1 = found"),
    status: models.ItemStatus | None = None,
    location_id: int | None = Query(default=None, gt=0),
    q: str | None = Query(default=None, max_length=100),
    include_withdrawn: bool = False,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    # NB: `type: Literal[0, 1] | None` does NOT work as a query parameter -
    # Pydantic will not coerce the string "0" from a query string to the int
    # literal 0, so every request 422s. ge/le on an int is the way to express
    # the same bound here.
    items = crud.list_items(
        db,
        type=type,
        status=status,
        location_id=location_id,
        q=q,
        include_withdrawn=include_withdrawn,
        limit=limit,
        offset=offset,
    )
    return [presenters.item_out(item) for item in items]


@router.get("/items/{item_id}", response_model=schemas.ItemResponse, responses=errors.errors(404))
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = crud.get_item(db, item_id)
    if item is None:
        raise APIError(404, errors.ITEM_NOT_FOUND, "item not found")
    return presenters.item_out(item)


@router.patch(
    "/items/{item_id}",
    response_model=schemas.ItemResponse,
    responses=errors.errors(404, 409, 422),
)
def update_item(item_id: int, changes: schemas.ItemUpdate, db: Session = Depends(get_db)):
    item = crud.get_item(db, item_id)
    if item is None:
        raise APIError(404, errors.ITEM_NOT_FOUND, "item not found")

    # exclude_unset keeps "field omitted" distinguishable from "field set to
    # null", which a plain model_dump() would collapse.
    payload = changes.model_dump(exclude_unset=True)
    if not payload:
        raise APIError(422, errors.EMPTY_UPDATE, "the request must change at least one field")
    if item.status not in crud.EDITABLE_STATUSES:
        raise APIError(409, errors.ITEM_CLOSED, f"a {item.status.value} post cannot be edited")

    new_location_id = payload.get("location_id")
    if new_location_id is not None and new_location_id != item.location_id:
        location = crud.get_location(db, new_location_id)
        if location is None:
            raise APIError(404, errors.LOCATION_NOT_FOUND, "location not found")
        if not location.is_active:
            raise APIError(409, errors.LOCATION_INACTIVE, "that location has been retired")

    item = crud.update_item(db, item, payload)
    messaging.emit("item.updated", item.id)
    return presenters.item_out(item)


@router.patch(
    "/items/{item_id}/status",
    response_model=schemas.ItemResponse,
    responses=errors.errors(404, 409, 422),
)
def update_item_status(
    item_id: int, change: schemas.ItemStatusUpdate, db: Session = Depends(get_db)
):
    item = crud.get_item(db, item_id)
    if item is None:
        raise APIError(404, errors.ITEM_NOT_FOUND, "item not found")

    new_status = models.ItemStatus(change.status)
    if new_status == item.status:
        return presenters.item_out(item)
    if new_status not in crud.CLIENT_TRANSITIONS[item.status]:
        raise APIError(
            409,
            errors.INVALID_STATUS_TRANSITION,
            f"an item cannot go from {item.status.value} to {new_status.value}",
        )
    if new_status is models.ItemStatus.OPEN and not item.location.is_active:
        raise APIError(
            409,
            errors.LOCATION_INACTIVE,
            "this post cannot be reopened because its location has been retired",
        )
    item = crud.set_item_status(db, item, new_status)
    withdrawn = new_status is models.ItemStatus.WITHDRAWN
    messaging.emit("item.withdrawn" if withdrawn else "item.updated", item.id)
    return presenters.item_out(item)


@router.delete("/items/{item_id}", status_code=204, responses=errors.errors(404, 409))
def withdraw_item(item_id: int, db: Session = Depends(get_db)):
    """Soft delete: sets status to 'withdrawn' and hides the post from search.
    Idempotent - withdrawing an already-withdrawn item is still a 204."""
    item = crud.get_item(db, item_id)
    if item is None:
        raise APIError(404, errors.ITEM_NOT_FOUND, "item not found")
    if item.status is not models.ItemStatus.WITHDRAWN:
        if models.ItemStatus.WITHDRAWN not in crud.CLIENT_TRANSITIONS[item.status]:
            raise APIError(
                409,
                errors.INVALID_STATUS_TRANSITION,
                f"a {item.status.value} post cannot be withdrawn; delete the match first",
            )
        crud.set_item_status(db, item, models.ItemStatus.WITHDRAWN)
        messaging.emit("item.withdrawn", item.id)
    return Response(status_code=204)


@router.delete(
    "/items/{item_id}/hard",
    status_code=204,
    dependencies=[admin],
    responses=errors.errors(401, 403, 404, 409),
)
def hard_delete_item(item_id: int, db: Session = Depends(get_db)):
    """Real deletion, for spam and cleanup."""
    item = crud.get_item(db, item_id)
    if item is None:
        raise APIError(404, errors.ITEM_NOT_FOUND, "item not found")
    upload_ids = crud.list_upload_ids(db, item_id)
    try:
        # Image rows go with it (ON DELETE CASCADE).
        crud.delete_item(db, item)
    except IntegrityError:
        # The FK RESTRICT is what actually stops this; catching it here is how
        # the client gets a 409 instead of a 500.
        db.rollback()
        raise APIError(
            409, errors.ITEM_HAS_MATCHES, "that item is in a match; delete the match first"
        ) from None
    if upload_ids:
        try:
            for upload_id in upload_ids:
                storage.delete(storage.pending_key(upload_id))
            storage.delete_prefix(storage.item_prefix(item_id))
        except (BotoCoreError, ClientError):
            # The row is already gone, so leftovers are unreferenced and private.
            log.exception("could not remove stored photos for deleted item %s", item_id)
    return Response(status_code=204)
