from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import crud
import errors
import schemas
from database.database import get_db
from errors import APIError
from database import models

router = APIRouter(tags=["matches"])


@router.post(
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


@router.get("/matches", response_model=list[schemas.MatchResponse])
def list_matches(
    db: Session = Depends(get_db),
    item_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return crud.list_matches(db, item_id=item_id, limit=limit, offset=offset)


@router.get(
    "/matches/{match_id}", response_model=schemas.MatchResponse, responses=errors.errors(404)
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


# There is deliberately no PATCH /matches/{id}. Changing a match to use a different
# items is not just an edit, the old pair must be changed back to 'open' and the
# new pair validated again, so we use DELETE + POST.


@router.delete("/matches/{match_id}", status_code=204, responses=errors.errors(404))
def delete_match(match_id: int, db: Session = Depends(get_db)):
    """Unmatch. Neither item is deleted; both go back to 'open' unless one has
    already been marked 'returned'."""
    match = crud.get_match(db, match_id)
    if match is None:
        raise APIError(404, errors.MATCH_NOT_FOUND, "match not found")
    crud.delete_match(db, match)
    return Response(status_code=204)
