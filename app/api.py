"""Lost & Found API. Every endpoint is in this one file, top to bottom:
items, then matches, then locations.

    uvicorn main:app --reload      # docs at http://127.0.0.1:8000/docs
"""

import logging
import os
import uuid
from typing import Annotated

from fastapi import Depends, FastAPI, Header, Query, Request, Response
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import crud
import errors
from database import models
import schemas
from database.database import Base, engine, get_db
from errors import APIError, register_error_handlers

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Lost & Found API", version="0.1.0")

# Points every kind of failure at the handlers in errors.py, so nothing escapes
# in FastAPI's default {"detail": "..."} shape.
register_error_handlers(app)


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    """Tags each request so a 5xx in the log can be matched to the id the user
    saw in the response.

    The gateway sets X-Request-ID on every proxied request and always
    overwrites whatever the client sent, so adopting it here makes the nginx
    access log and the app log share one id. If you ever expose uvicorn
    directly, drop the header lookup - a client could otherwise choose its own
    id and muddy the logs."""
    request.state.request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response

# No migration tool by design. When a column changes, drop the database and let
# this rebuild it; create_all never ALTERs an existing table.
Base.metadata.create_all(bind=engine)


# --- admin placeholder ------------------------------------------------------
# Stands in for real auth until user_id lands. Replace this one function and
# every admin route below follows.
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dev-admin-token")


def require_admin(x_admin_token: Annotated[str | None, Header()] = None) -> None:
    if x_admin_token is None:
        raise APIError(401, errors.UNAUTHENTICATED, "authentication required")
    if x_admin_token != ADMIN_TOKEN:
        raise APIError(403, errors.FORBIDDEN, "admin access required")


admin = Depends(require_admin)


# --- items ------------------------------------------------------------------

@app.post(
    "/items",
    response_model=schemas.ItemResponse,
    status_code=201,
    responses=errors.errors(404, 409, 422),
)
def create_item(item: schemas.ItemCreate, db: Session = Depends(get_db)):
    location = crud.get_location(db, item.location_id)
    if location is None:
        raise APIError(404, errors.LOCATION_NOT_FOUND, "location not found")
    if not location.is_active:
        raise APIError(
            409, errors.LOCATION_INACTIVE, "that location has been retired"
        )
    return crud.create_item(db, item)


@app.get("/items", response_model=list[schemas.ItemResponse])
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
    return crud.list_items(
        db,
        type=type,
        status=status,
        location_id=location_id,
        q=q,
        include_withdrawn=include_withdrawn,
        limit=limit,
        offset=offset,
    )


@app.get("/items/{item_id}", response_model=schemas.ItemResponse, responses=errors.errors(404))
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = crud.get_item(db, item_id)
    if item is None:
        raise APIError(404, errors.ITEM_NOT_FOUND, "item not found")
    return item


@app.patch(
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

    return crud.update_item(db, item, payload)


@app.patch(
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
        return item
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
    return crud.set_item_status(db, item, new_status)


@app.delete("/items/{item_id}", status_code=204, responses=errors.errors(404, 409))
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
    return Response(status_code=204)


@app.delete(
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
    try:
        crud.delete_item(db, item)
    except IntegrityError:
        # The FK RESTRICT is what actually stops this; catching it here is how
        # the client gets a 409 instead of a 500.
        db.rollback()
        raise APIError(
            409, errors.ITEM_HAS_MATCHES, "that item is in a match; delete the match first"
        ) from None
    return Response(status_code=204)


# --- matches ----------------------------------------------------------------

@app.post(
    "/matches",
    response_model=schemas.MatchResponse,
    status_code=201,
    responses=errors.errors(404, 409, 422),
)
def create_match(match: schemas.MatchCreate, db: Session = Depends(get_db)):
    """Pairs a lost post with a found post and moves both to 'matched'."""
    if match.lost_item_id == match.found_item_id:
        raise APIError(422, errors.MATCH_SELF, "an item cannot be matched with itself")

    lost = crud.get_item(db, match.lost_item_id)
    if lost is None:
        raise APIError(404, errors.ITEM_NOT_FOUND, "lost item not found")
    found = crud.get_item(db, match.found_item_id)
    if found is None:
        raise APIError(404, errors.ITEM_NOT_FOUND, "found item not found")

    # The database cannot check a column against another row, so the type rule
    # is enforced here, as the spec says.
    if lost.type != models.ItemType.LOST:
        raise APIError(
            422, errors.ITEM_TYPE_MISMATCH, "lost_item_id points at a found post"
        )
    if found.type != models.ItemType.FOUND:
        raise APIError(
            422, errors.ITEM_TYPE_MISMATCH, "found_item_id points at a lost post"
        )

    for item in (lost, found):
        if item.status is not models.ItemStatus.OPEN:
            raise APIError(
                409,
                errors.ITEM_NOT_OPEN,
                f"item {item.id} is {item.status.value} and cannot be matched",
            )

    try:
        return crud.create_match(db, lost, found)
    except IntegrityError:
        # uq_matches_item_pair. The status check above already covers the
        # ordinary case; this catches two requests racing between the SELECT
        # and the INSERT.
        db.rollback()
        raise APIError(
            409, errors.MATCH_ALREADY_EXISTS, "those two items are already matched"
        ) from None


@app.get("/matches", response_model=list[schemas.MatchResponse])
def list_matches(
    db: Session = Depends(get_db),
    item_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return crud.list_matches(db, item_id=item_id, limit=limit, offset=offset)


@app.get(
    "/matches/{match_id}", response_model=schemas.MatchResponse, responses=errors.errors(404)
)
def get_match(match_id: int, db: Session = Depends(get_db)):
    match = crud.get_match(db, match_id)
    if match is None:
        raise APIError(404, errors.MATCH_NOT_FOUND, "match not found")
    return match


@app.get(
    "/items/{item_id}/matches",
    response_model=list[schemas.MatchResponse],
    responses=errors.errors(404),
)
def matches_by_item(item_id: int, db: Session = Depends(get_db)):
    if crud.get_item(db, item_id) is None:
        raise APIError(404, errors.ITEM_NOT_FOUND, "item not found")
    return crud.list_matches(db, item_id=item_id)


# There is deliberately no PATCH /matches/{id}. Repointing a match at different
# items is not an edit: the old pair has to be released back to 'open' and the
# new pair re-validated, which is exactly DELETE + POST. It would also quietly
# falsify created_at.


@app.delete("/matches/{match_id}", status_code=204, responses=errors.errors(404))
def delete_match(match_id: int, db: Session = Depends(get_db)):
    """Unmatch. Neither item is deleted; both go back to 'open' unless one has
    already been marked 'returned'."""
    match = crud.get_match(db, match_id)
    if match is None:
        raise APIError(404, errors.MATCH_NOT_FOUND, "match not found")
    crud.delete_match(db, match)
    return Response(status_code=204)


# --- locations --------------------------------------------------------------

@app.post(
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


@app.get("/locations", response_model=list[schemas.LocationAdminResponse])
def list_locations(
    db: Session = Depends(get_db),
    include_inactive: bool = False,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Active locations only by default, which is what the 'post an item'
    dropdown wants. is_active is included here so an admin screen can tell
    retired entries apart."""
    return crud.list_locations(
        db, include_inactive=include_inactive, limit=limit, offset=offset
    )


@app.get(
    "/locations/{location_id}",
    response_model=schemas.LocationResponse,
    responses=errors.errors(404),
)
def get_location(location_id: int, db: Session = Depends(get_db)):
    location = crud.get_location(db, location_id)
    if location is None:
        raise APIError(404, errors.LOCATION_NOT_FOUND, "location not found")
    return location


@app.get(
    "/locations/{location_id}/items",
    response_model=list[schemas.ItemResponse],
    responses=errors.errors(404),
)
def items_by_location(location_id: int, db: Session = Depends(get_db)):
    if crud.get_location(db, location_id) is None:
        raise APIError(404, errors.LOCATION_NOT_FOUND, "location not found")
    return crud.list_items(db, location_id=location_id)


@app.patch(
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


@app.delete(
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


@app.post(
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


@app.delete(
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


# --- meta -------------------------------------------------------------------

@app.get("/health")
def health(db: Session = Depends(get_db)):
    """503 if Postgres is unreachable; the OperationalError handler formats it
    and nothing from psycopg reaches the client."""
    db.execute(text("SELECT 1"))
    return {"status": "ok"}