"""Builds response models from database rows, adding the download URLs that
only the storage port can produce."""

import schemas
from database import models
from ports import storage


def item_out(item: models.Item) -> schemas.ItemResponse:
    response = schemas.ItemResponse.model_validate(item)
    if item.photo is not None:
        response.photo_url = storage.download_url(item.photo.photo_key)
    return response


def image_out(image: models.Image) -> schemas.ImageResponse:
    response = schemas.ImageResponse.model_validate(image)
    if image.status is models.ImageStatus.READY:
        response.photo_url = storage.download_url(image.photo_key)
    return response
