import crud
import errors
import messaging
import metrics
import schemas
from auth import admin, login_required
from database import models
from database.database import get_db
from errors import APIError
from fastapi import APIRouter, Depends, Query, Response
from matching.matcher import MAX_SUGGESTIONS
from pika.exceptions import AMQPError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

router = APIRouter(tags=["matches"])


@router.post(
    "/matches",
    response_model=schemas.MatchResponse,
    status_code=201,
    dependencies=[login_required],
    responses=errors.errors(401, 404, 409, 422),
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
        row = crud.create_match(db, lost, found)
    except IntegrityError:
        # uq_matches_item_pair. The status check above already covers the
        # ordinary case; this catches two requests racing between the SELECT
        # and the INSERT.
        db.rollback()
        raise APIError(
            409, errors.MATCH_ALREADY_EXISTS, "those two items are already matched"
        ) from None
    metrics.MATCHES_CONFIRMED.inc()
    messaging.emit_event(
        "match.confirmed",
        {"match_id": row.id, "lost_item_id": lost.id, "found_item_id": found.id},
    )
    return row


@router.get("/matches", response_model=list[schemas.MatchResponse])
def list_matches(
    db: Session = Depends(get_db),
    item_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return crud.list_matches(db, item_id=item_id, limit=limit, offset=offset)


@router.get(
    "/matches/{match_id}",
    response_model=schemas.MatchResponse,
    responses=errors.errors(404),
)
def get_match(match_id: int, db: Session = Depends(get_db)):
    match = crud.get_match(db, match_id)
    if match is None:
        raise APIError(404, errors.MATCH_NOT_FOUND, "match not found")
    return match


@router.get(
    "/items/{item_id}/matches",
    response_model=list[schemas.MatchResponse],
    responses=errors.errors(404),
)
def matches_by_item(item_id: int, db: Session = Depends(get_db)):
    if crud.get_item(db, item_id) is None:
        raise APIError(404, errors.ITEM_NOT_FOUND, "item not found")
    return crud.list_matches(db, item_id=item_id)


# There is deliberately no update for matches. Changing a match to use a different
# items should not be allowed, and the old pair should instead be changed back to 'open' and the
# new pair validated again. So dont update, use DELETE + POST. See "No update for matches"
# under Decisions in the README.


@router.delete(
    "/matches/{match_id}",
    status_code=204,
    dependencies=[login_required],
    responses=errors.errors(401, 404),
)
def delete_match(match_id: int, db: Session = Depends(get_db)):
    """Unmatch. Neither item is deleted; both go back to 'open' unless one has
    already been marked 'returned'."""
    match = crud.get_match(db, match_id)
    if match is None:
        raise APIError(404, errors.MATCH_NOT_FOUND, "match not found")
    for item in crud.delete_match(db, match):
        messaging.queue_matching(item.id)
    return Response(status_code=204)


@router.get(
    "/items/{item_id}/potential-matches",
    response_model=list[schemas.PotentialMatchResponse],
    responses=errors.errors(404),
)
def potential_matches_by_item(item_id: int, db: Session = Depends(get_db)):
    """Suggestions from the matching worker, best first. Pairs where either item
    is no longer open are left out. Confirm the right one with POST /matches."""
    if crud.get_item(db, item_id) is None:
        raise APIError(404, errors.ITEM_NOT_FOUND, "item not found")
    return crud.list_potential_matches(db, item_id, limit=MAX_SUGGESTIONS)


@router.post(
    "/items/{item_id}/match-search",
    response_model=schemas.MatchSearchResponse,
    status_code=202,
    dependencies=[admin],
    responses=errors.errors(401, 403, 404, 409, 503),
)
def queue_match_search(item_id: int, db: Session = Depends(get_db)):
    """Queues a fresh matching run for one item; the worker then replaces its
    suggestions. Unlike posting an item, this fails if the job can't be queued,
    so the admin knows to try again."""
    item = crud.get_item(db, item_id)
    if item is None:
        raise APIError(404, errors.ITEM_NOT_FOUND, "item not found")
    if item.status is not models.ItemStatus.OPEN:
        raise APIError(
            409,
            errors.ITEM_NOT_OPEN,
            f"item {item.id} is {item.status.value} and cannot be matched",
        )
    try:
        messaging.publish_matching_job(item.id)
    except AMQPError:
        raise APIError(
            503,
            errors.SERVICE_UNAVAILABLE,
            "the matching queue is unavailable, please try again",
        ) from None
    return schemas.MatchSearchResponse(item_id=item.id)
