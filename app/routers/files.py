"""File endpoints. These are files a user keeps as proof of ownership when
claiming an item, like a receipt or a photo of a serial number.

Unlike item photos these go through the API, so all the checks happen before
anything is written. Uploads write to the store first and then the database,
and deletes do the opposite, so if something fails partway we end up with an
extra object and not a row pointing at nothing. More detail is in
milestones/milestone4/STORAGE_DESIGN.md.
"""

import logging
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Query, Response, UploadFile
from sqlalchemy.orm import Session

import crud
import errors
import image_processing
import schemas
from database import models
from database.database import get_db
from errors import APIError
from ports import storage

log = logging.getLogger("lostfound")

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_FILES = 5

# type detected by `file -k` -> extension used in the key
# (no html/svg or anything else a browser would run)
ALLOWED_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/heic": "heic",
    "application/pdf": "pdf",
}

router = APIRouter(prefix="/files", tags=["files"])


def check(upload: UploadFile) -> tuple[bytes, str]:
    """413 or 400, or the bytes and their real content type."""
    data = upload.file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise APIError(
            413, errors.FILE_TOO_LARGE, f"each file must be at most {MAX_FILE_BYTES // 2**20} MB"
        )
    matches = image_processing.sniff(data)
    if not matches or any(match not in ALLOWED_TYPES for match in matches):
        raise APIError(
            400,
            errors.UNSUPPORTED_FILE_TYPE,
            "only JPEG, PNG, WebP, HEIC and PDF files are accepted",
        )
    return data, matches[0]


def display_name(filename: str | None) -> str:
    """Cleans up the client's filename. Only used for display and search, never in a key."""
    name = (filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    return name[:255] or "unnamed"


def discard(keys: list[str]) -> None:
    for key in keys:
        try:
            storage.delete(key)
        except Exception:
            # not a big deal, the storage report will find it
            log.exception("could not remove %s after a failed upload", key)


def save(db: Session, user_id: int, uploads: list[UploadFile]) -> list[models.File]:
    if crud.get_user(db, user_id) is None:
        raise APIError(404, errors.USER_NOT_FOUND, "user not found")
    # Every file passes before any of them is written.
    checked = [check(upload) for upload in uploads]

    rows, written = [], []
    try:
        for upload, (data, content_type) in zip(uploads, checked):
            upload_id = str(uuid.uuid4())
            key = storage.file_key(user_id, upload_id, ALLOWED_TYPES[content_type])
            name = display_name(upload.filename)
            storage.write(key, data, content_type, upload_id, name)
            written.append(key)
            rows.append(
                models.File(
                    user_id=user_id,
                    key=key,
                    original_filename=name,
                    content_type=content_type,
                    size_bytes=len(data),
                )
            )
        return crud.add_files(db, rows)
    except Exception:
        discard(written)
        raise


@router.post(
    "",
    response_model=schemas.FileResponse,
    status_code=201,
    responses=errors.errors(400, 404, 413, 422, 503),
)
def upload_file(
    file: UploadFile, user_id: int = Form(gt=0), db: Session = Depends(get_db)
):
    return save(db, user_id, [file])[0]


@router.post(
    "/batch",
    response_model=list[schemas.FileResponse],
    status_code=201,
    responses=errors.errors(400, 404, 413, 422, 503),
)
def upload_files(
    files: list[UploadFile], user_id: int = Form(gt=0), db: Session = Depends(get_db)
):
    """All or nothing: one bad file and none of them are stored."""
    if len(files) > MAX_FILES:
        raise APIError(413, errors.TOO_MANY_FILES, f"at most {MAX_FILES} files per request")
    return save(db, user_id, files)


@router.get("", response_model=list[schemas.FileResponse])
def list_files(
    db: Session = Depends(get_db),
    user_id: int | None = Query(default=None, gt=0),
    content_type: str | None = Query(default=None, max_length=100),
    name: str | None = Query(
        default=None, max_length=100, description="Part of the original filename"
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return crud.list_files(
        db, user_id=user_id, content_type=content_type, name=name, limit=limit, offset=offset
    )


@router.get("/{file_id}", response_model=schemas.FileResponse, responses=errors.errors(404))
def get_file(file_id: int, db: Session = Depends(get_db)):
    row = crud.get_file(db, file_id)
    if row is None:
        raise APIError(404, errors.FILE_NOT_FOUND, "file not found")
    return row


@router.get(
    "/{file_id}/content",
    response_class=Response,
    responses={200: {"content": {t: {} for t in ALLOWED_TYPES}}, **errors.errors(404, 503)},
)
def download_file(file_id: int, db: Session = Depends(get_db)):
    """The bytes, with the content type recorded at upload."""
    row = crud.get_file(db, file_id)
    if row is None:
        raise APIError(404, errors.FILE_NOT_FOUND, "file not found")
    data = storage.read(row.key, MAX_FILE_BYTES)
    if data is None:
        log.error("file %s has a row but no object at %s", row.id, row.key)
        raise APIError(404, errors.FILE_NOT_FOUND, "file not found")
    return Response(
        content=data,
        media_type=row.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(row.original_filename)}",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/{file_id}", status_code=204, responses=errors.errors(404))
def delete_file(file_id: int, db: Session = Depends(get_db)):
    row = crud.get_file(db, file_id)
    if row is None:
        raise APIError(404, errors.FILE_NOT_FOUND, "file not found")
    key = row.key
    crud.delete_file(db, row)
    # row is already gone, so if this fails it just leaves an extra object
    # (the storage report finds those). Still return 204.
    discard([key])
    return Response(status_code=204)
