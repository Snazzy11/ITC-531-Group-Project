# The API never handles image bytes. The client PUTs the file straight to the
# store with upload_url, then calls /complete; the image worker does the rest.
# See milestones/milestone4/STORAGE_DESIGN.md.

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import messaging
import presenters
import crud
import errors
import schemas
from auth import current_user, require_owner_or_admin
from database.database import get_db
from database.models import User
from errors import APIError
from database import models
from ports import storage

router = APIRouter(tags=["images"])


@router.post(
    "/items/{item_id}/images",
    response_model=schemas.ImageUploadResponse,
    status_code=201,
    responses=errors.errors(401, 403, 404, 409),
)
def start_image_upload(
    item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Returns a presigned upload_url. A finished upload replaces the item's
    current photo."""
    item = crud.get_item(db, item_id)
    if item is None:
        raise APIError(404, errors.ITEM_NOT_FOUND, "item not found")
    require_owner_or_admin(user, item.user_id)
    if item.status not in crud.EDITABLE_STATUSES:
        raise APIError(409, errors.ITEM_CLOSED, f"a {item.status.value} post cannot be edited")
    image = crud.create_image(db, item)
    return schemas.ImageUploadResponse(
        upload_id=image.upload_id,
        status=image.status,
        upload_url=storage.upload_url(storage.pending_key(image.upload_id)),
        expires_in=storage.UPLOAD_URL_SECONDS,
    )


@router.post(
    "/items/{item_id}/images/{upload_id}/complete",
    response_model=schemas.ImageResponse,
    status_code=202,
    responses=errors.errors(401, 403, 404, 409),
)
def complete_image_upload(
    item_id: int,
    upload_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Call once the PUT to upload_url has succeeded. Idempotent: an upload
    that is already queued or finished is returned as it is."""
    item = crud.get_item(db, item_id)
    if item is None:
        raise APIError(404, errors.ITEM_NOT_FOUND, "item not found")
    require_owner_or_admin(user, item.user_id)
    image = crud.get_image(db, item_id, upload_id)
    if image is None:
        raise APIError(404, errors.IMAGE_NOT_FOUND, "image not found")
    if image.status is models.ImageStatus.AWAITING_UPLOAD:
        if not storage.exists(storage.pending_key(upload_id)):
            raise APIError(
                409, errors.UPLOAD_NOT_RECEIVED, "nothing has been uploaded to upload_url yet"
            )
        # Queue before recording it: if the broker is down this fails, the
        # status is untouched, and the client can call /complete again.
        messaging.publish_image_job(item_id, upload_id)
        image = crud.set_image_status(db, image, models.ImageStatus.PROCESSING)
    return presenters.image_out(image)


@router.get(
    "/items/{item_id}/images/{upload_id}",
    response_model=schemas.ImageResponse,
    responses=errors.errors(404),
)
def get_image_status(item_id: int, upload_id: str, db: Session = Depends(get_db)):
    image = crud.get_image(db, item_id, upload_id)
    if image is None:
        raise APIError(404, errors.IMAGE_NOT_FOUND, "image not found")
    return presenters.image_out(image)
