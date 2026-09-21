"""Request and response schemas.

Two deliberate departures from the draft you sent:

1. `ItemResponse` does not inherit the request-side `description: str`
   constraint. The column is nullable, so a row with a NULL description would
   fail *response* validation and turn a healthy GET into a 500. Here
   `description` is optional in the shared base, which is safe in both
   directions.
2. `status` is typed as the real `ItemStatus` enum, not a Literal of strings.
   Reading from the ORM yields an enum member, and `str`-Enum members hash by
   name ("OPEN"), not value ("open"), so Literal matching is a footgun. The
   JSON on the wire is identical: "open", "matched", ...

`extra="forbid"` on the request models is optional but cheap insurance: a
client that POSTs {"nmae": ...} gets a 422 instead of silently creating an
item called "".
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from database.models import ItemStatus

REQUEST = ConfigDict(extra="forbid", str_strip_whitespace=True)


# --- items ------------------------------------------------------------------

class ItemBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    location_id: int = Field(gt=0)


class ItemCreate(ItemBase):
    model_config = REQUEST

    type: Literal[0, 1]  # 0 = lost, 1 = found


class ItemUpdate(BaseModel):
    model_config = REQUEST

    # `type` is absent on purpose: flipping lost <-> found would invalidate any
    # match the item belongs to. Withdraw and repost instead.
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    location_id: int | None = Field(default=None, gt=0)


class ItemStatusUpdate(BaseModel):
    model_config = REQUEST

    # "matched" is absent: only creating or deleting a Match may set it.
    status: Literal["open", "returned", "withdrawn", "expired"]


class ItemResponse(ItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: Literal[0, 1]
    status: ItemStatus
    created_at: datetime


# --- matches ----------------------------------------------------------------

class MatchCreate(BaseModel):
    model_config = REQUEST

    lost_item_id: int = Field(gt=0)
    found_item_id: int = Field(gt=0)


class MatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lost_item_id: int
    found_item_id: int
    created_at: datetime


# --- locations --------------------------------------------------------------

class LocationBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    coordinates: str = Field(min_length=3, max_length=50)
    description: str | None = Field(default=None, max_length=500)


class LocationCreate(LocationBase):
    model_config = REQUEST


class LocationUpdate(BaseModel):
    model_config = REQUEST

    name: str | None = Field(default=None, min_length=1, max_length=100)
    coordinates: str | None = Field(default=None, min_length=3, max_length=50)
    description: str | None = Field(default=None, max_length=500)


class LocationResponse(LocationBase):
    """`is_active` is omitted: it only governs whether a location can be picked
    for a new post, and retired locations still appear on old posts."""

    model_config = ConfigDict(from_attributes=True)

    id: int


class LocationAdminResponse(LocationResponse):
    """Same thing plus `is_active`, so an admin list can tell retired entries
    apart."""

    is_active: bool