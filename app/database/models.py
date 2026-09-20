import enum

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
    true
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.database import Base

class ItemType(enum.IntEnum):
    LOST = 0
    FOUND = 1

class ItemStatus(str, enum.Enum):
    OPEN = "open"
    MATCHED = "matched"
    RETURNED = "returned"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"

class Location(Base):
    __tablename__ = "locations"


    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    coordinates = Column(String(50), nullable=False)
    description = Column(String(500))
    is_active = Column(Boolean, nullable=False, server_default=true())


    items = relationship("Item", back_populates="location", passive_deletes="all")

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
    # user_id = Column(Integer) # would be a foreign key later on
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    location = relationship("Location", back_populates="items")
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
        "Item", foreign_keys="lost_item_id", back_populates="lost_matches"
    )
    found_item = relationship(
        "Item", foreign_keys="found_item_id", back_populates="found_matches"
    )
