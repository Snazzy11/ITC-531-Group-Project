import enum
import uuid
from typing import List

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    and_,
    true,
)
from sqlalchemy.orm import Mapped, relationship
from sqlalchemy.sql import func

from database.database import Base


class ItemType(enum.IntEnum):
    LOST = 0
    FOUND = 1


class ItemStatus(str, enum.Enum):
    OPEN = "open" # Fully unmatched item; also for items with proposed but unclaimed matches
    MATCHED = "matched" # Matched to another item
    RETURNED = "returned" # Matched and returned to use
    WITHDRAWN = "withdrawn" # Removed from application by the user, for any reason
    EXPIRED = "expired" # Stale for too long


class ImageStatus(str, enum.Enum):
    AWAITING_UPLOAD = "awaiting_upload"
    PROCESSING = "processing"
    READY = "ready"
    REJECTED = "rejected"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    user_display_name = Column(String(50), nullable=False, unique=True)
    user_real_name = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    password_hash = Column(String(255), nullable=False) # TODO change later
    is_admin = Column(Boolean, nullable=False)

    items = relationship("Item", back_populates="user_id_relation")


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    coordinates = Column(String(50), nullable=False)
    description = Column(String(500))
    is_active = Column(Boolean, nullable=False, server_default=true())

    items: Mapped[List["Item"]] = relationship(back_populates="location")



class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint("type IN (0, 1)", name="ck_items_type"),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(1000))
    type = Column(Integer, nullable=False, index=True)
    status = Column(
        Enum(
            ItemStatus,
            name="item_status",
            native_enum=False,
            length=20,
            validate_strings=True,
            values_callable=lambda status: [member.value for member in status],
        ),
        nullable=False,
        default=ItemStatus.OPEN,
        server_default=ItemStatus.OPEN.value,
        index=True,
    )
    location_id = Column(
        Integer,
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    location = relationship("Location", back_populates="items")

    # user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user_id_relation: Mapped["User"] = relationship(back_populates="items")

    # Only a processed image is ever shown; the worker keeps at most one per item.
    photo = relationship(
        "Image",
        primaryjoin=lambda: and_(Image.item_id == Item.id, Image.status == ImageStatus.READY),
        uselist=False,
        viewonly=True,
        lazy="selectin",
    )
    lost_matches = relationship(
        "Match",
        foreign_keys="Match.lost_item_id",
        back_populates="lost_item",
        passive_deletes="all",
    )
    found_matches = relationship(
        "Match",
        foreign_keys="Match.found_item_id",
        back_populates="found_item",
        passive_deletes="all",
    )

    @property
    def matches(self):
        return self.lost_matches + self.found_matches

class Image(Base):
    """One upload attempt. Rows are created when an upload link is issued; the
    image worker fills in the rest."""

    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(
        Integer,
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    upload_id = Column(
        String(36),
        nullable=False,
        unique=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )
    status = Column(
        Enum(
            ImageStatus,
            name="image_status",
            native_enum=False,
            length=20,
            validate_strings=True,
            values_callable=lambda status: [member.value for member in status],
        ),
        nullable=False,
        default=ImageStatus.AWAITING_UPLOAD,
        server_default=ImageStatus.AWAITING_UPLOAD.value,
        index=True,
    )
    photo_key = Column(String(255))
    # What `file -k` said the original upload was, and its size.
    content_type = Column(String(100))
    size_bytes = Column(Integer)
    reject_reason = Column(String(200))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at = Column(DateTime(timezone=True))


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint("lost_item_id", "found_item_id", name="uq_matches_item_pair"),
        CheckConstraint("lost_item_id <> found_item_id", name="ck_matches_distinct_items"),
    )

    id = Column(Integer, primary_key=True, index=True)
    lost_item_id = Column(
        Integer,
        ForeignKey("items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    found_item_id = Column(
        Integer,
        ForeignKey("items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    lost_item = relationship(
        "Item", foreign_keys=[lost_item_id], back_populates="lost_matches"
    )
    found_item = relationship(
        "Item", foreign_keys=[found_item_id], back_populates="found_matches"
    )