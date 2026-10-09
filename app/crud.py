"""Database access. Every function takes a Session and returns rows or None -
no HTTP knowledge, no exceptions raised on purpose. The routers decide what a
None or an IntegrityError means to a client.

The one piece of policy that lives here is CLIENT_TRANSITIONS, because it
describes the item lifecycle rather than any single endpoint.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from database import models
import schemas
from database.models import File, Item, Match, Location, User
from password_util import hash_password

# Transitions a client may ask for directly via PATCH /items/{id}/status.
# Anything -> MATCHED and MATCHED -> OPEN are system-only: they happen when a
# match is created or deleted. That is why "matched" is not in
# schemas.ItemStatusUpdate.
CLIENT_TRANSITIONS = {
    models.ItemStatus.OPEN: {models.ItemStatus.WITHDRAWN, models.ItemStatus.EXPIRED},
    models.ItemStatus.MATCHED: {models.ItemStatus.RETURNED},
    models.ItemStatus.WITHDRAWN: {models.ItemStatus.OPEN},
    models.ItemStatus.EXPIRED: {models.ItemStatus.OPEN},
    models.ItemStatus.RETURNED: set(),  # terminal
}

EDITABLE_STATUSES = {
    models.ItemStatus.OPEN,
    models.ItemStatus.MATCHED,
    models.ItemStatus.WITHDRAWN,
    models.ItemStatus.EXPIRED,
}


# items

def create_item(db: Session, item: schemas.ItemCreate, user_id: int) -> models.Item:
    # status is not passed: the column defaults to 'open'.
    row = models.Item(**item.model_dump(), user_id=user_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_item(db: Session, item_id: int) -> type[Item] | None:
    return db.query(models.Item).filter(models.Item.id == item_id).first()


def list_items(
    db: Session,
    type: int | None = None,
    status: models.ItemStatus | None = None,
    location_id: int | None = None,
    q: str | None = None,
    include_withdrawn: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> list[type[Item]]:
    query = db.query(models.Item)

    if type is not None:
        query = query.filter(models.Item.type == type)

    if status is not None:
        query = query.filter(models.Item.status == status)
    elif not include_withdrawn:
        # Withdrawn posts are hidden from search. That is what "deleting" a
        # post means for a normal user.
        query = query.filter(models.Item.status != models.ItemStatus.WITHDRAWN)

    if location_id is not None:
        query = query.filter(models.Item.location_id == location_id)

    if q:
        pattern = f"%{q}%"
        query = query.filter(
            models.Item.name.ilike(pattern) | models.Item.description.ilike(pattern)
        )

    return (
        query.order_by(models.Item.created_at.desc(), models.Item.id.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )


def update_item(db: Session, item: models.Item, changes: dict) -> models.Item:
    for field, value in changes.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


def set_item_status(
    db: Session, item: models.Item, status: models.ItemStatus
) -> models.Item:
    item.status = status
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, item: models.Item) -> None:
    """Real row deletion. The FK RESTRICT on matches is the actual guard, so
    this raises IntegrityError if the item is still in a match."""
    db.delete(item)
    db.commit()


# matches

def create_match(db: Session, lost: models.Item, found: models.Item) -> models.Match:
    """Creates the pair and moves both items to 'matched' in one transaction,
    so a unique-constraint violation rolls the status changes back too."""
    row = models.Match(lost_item_id=lost.id, found_item_id=found.id)
    lost.status = models.ItemStatus.MATCHED
    found.status = models.ItemStatus.MATCHED
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_match(db: Session, match_id: int) -> models.Match | None:
    return db.query(models.Match).filter(models.Match.id == match_id).first()


def list_matches(
    db: Session, item_id: int | None = None, limit: int = 20, offset: int = 0
) -> list[type[Match]]:
    query = db.query(models.Match)

    if item_id is not None:
        query = query.filter(
            (models.Match.lost_item_id == item_id)
            | (models.Match.found_item_id == item_id)
        )

    return (
        query.order_by(models.Match.created_at.desc(), models.Match.id.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )


def delete_match(db: Session, match: models.Match) -> None:
    """Unmatch. Both items go back to 'open', but only if they are still
    'matched' - one already marked 'returned' stays returned."""
    for item in (match.lost_item, match.found_item):
        if item is not None and item.status == models.ItemStatus.MATCHED:
            item.status = models.ItemStatus.OPEN
    db.delete(match)
    db.commit()


# locations

def create_location(db: Session, location: schemas.LocationCreate) -> models.Location:
    row = models.Location(**location.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_location(db: Session, location_id: int) -> type[Location] | None:
    return db.query(models.Location).filter(models.Location.id == location_id).first()


def list_locations(
    db: Session, include_inactive: bool = False, limit: int = 100, offset: int = 0
) -> list[type[Location]]:
    query = db.query(models.Location)

    if not include_inactive:
        query = query.filter(models.Location.is_active.is_(True))

    return query.order_by(models.Location.name).limit(limit).offset(offset).all()


def update_location(
    db: Session, location: models.Location, changes: dict
) -> models.Location:
    for field, value in changes.items():
        setattr(location, field, value)
    db.commit()
    db.refresh(location)
    return location


def set_location_active(
    db: Session, location: models.Location, is_active: bool
) -> models.Location:
    location.is_active = is_active
    db.commit()
    db.refresh(location)
    return location


def count_items_at_location(db: Session, location_id: int) -> int:
    return (
        db.query(models.Item).filter(models.Item.location_id == location_id).count()
    )


def delete_location(db: Session, location: models.Location) -> None:
    db.delete(location)
    db.commit()


# images

def create_image(db: Session, item: models.Item) -> models.Image:
    # upload_id and status come from the column defaults.
    row = models.Image(item_id=item.id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_image(db: Session, item_id: int, upload_id: str) -> models.Image | None:
    return (
        db.query(models.Image)
        .filter(models.Image.item_id == item_id, models.Image.upload_id == upload_id)
        .first()
    )


def list_upload_ids(db: Session, item_id: int) -> list[str]:
    rows = db.query(models.Image.upload_id).filter(models.Image.item_id == item_id)
    return [row.upload_id for row in rows]


def set_image_status(
    db: Session, image: models.Image, status: models.ImageStatus
) -> models.Image:
    image.status = status
    db.commit()
    db.refresh(image)
    return image


def mark_image_rejected(db: Session, image: models.Image, reason: str) -> None:
    image.status = models.ImageStatus.REJECTED
    image.reject_reason = reason
    image.processed_at = datetime.now(timezone.utc)
    db.commit()


def mark_image_ready(
    db: Session, image: models.Image, photo_key: str, content_type: str, size_bytes: int
) -> list[str]:
    """Makes this the item's photo and deletes the previous one's row in the
    same transaction, so an item never has two. Returns the replaced photo
    keys for the caller to delete from the store after the commit."""
    replaced = (
        db.query(models.Image)
        .filter(
            models.Image.item_id == image.item_id,
            models.Image.status == models.ImageStatus.READY,
            models.Image.id != image.id,
        )
        .all()
    )
    replaced_keys = [old.photo_key for old in replaced]
    for old in replaced:
        db.delete(old)

    image.status = models.ImageStatus.READY
    image.photo_key = photo_key
    image.content_type = content_type
    image.size_bytes = size_bytes
    image.processed_at = datetime.now(timezone.utc)
    db.commit()
    return replaced_keys


# files

def add_files(db: Session, rows: list[models.File]) -> list[models.File]:
    """One transaction for the whole batch, so a multi-file upload is indexed
    all or not at all."""
    db.add_all(rows)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def get_file(db: Session, file_id: int) -> File | None:
    return db.query(models.File).filter(models.File.id == file_id).first()


def list_files(
    db: Session,
    user_id: int | None = None,
    content_type: str | None = None,
    name: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[type[File]]:
    query = db.query(models.File)

    if user_id is not None:
        query = query.filter(models.File.user_id == user_id)

    if content_type:
        query = query.filter(models.File.content_type == content_type)

    if name:
        query = query.filter(models.File.original_filename.ilike(f"%{name}%"))

    return (
        query.order_by(models.File.uploaded_at.desc(), models.File.id.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )


def delete_file(db: Session, row: models.File) -> None:
    db.delete(row)
    db.commit()


# users

def get_or_create_role(db: Session, name: str) -> models.Role:
    role = db.scalar(select(models.Role).where(models.Role.name == name))
    if role is None:
        role = models.Role(name=name)
        db.add(role)
        db.flush()
    return role


def create_user(db: Session, user: schemas.UserCreate, role: str = "user") -> User:
    """Raises password_util.PasswordTooLongError for a password over 72 bytes."""
    row = models.User(
        display_name=user.display_name,
        real_name=user.real_name,
        password_hash=hash_password(user.password),
        roles=[get_or_create_role(db, role)],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def seed_auth(db: Session, admin_name: str | None, admin_password: str | None) -> None:
    """Idempotent startup step: make sure the roles exist and, when both
    settings are given, that the bootstrap admin account exists."""
    get_or_create_role(db, "user")
    admin_role = get_or_create_role(db, "admin")
    if admin_name and admin_password:
        existing = db.scalar(select(User).where(User.display_name == admin_name))
        if existing is None:
            db.add(User(
                display_name=admin_name,
                real_name="Administrator",
                password_hash=hash_password(admin_password),
                roles=[admin_role],
            ))
        elif admin_role not in existing.roles:
            existing.roles.append(admin_role)
    db.commit()


def get_user(db: Session, user_id: int) -> User | None:
    return db.query(models.User).filter(models.User.id == user_id).first()


def list_users(db: Session, limit: int = 100, offset: int = 0) -> list[type[User]]:
    query = db.query(models.User)
    return query.order_by(models.User.id).limit(limit).offset(offset).all()
