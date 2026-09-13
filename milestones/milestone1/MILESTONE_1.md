# Part 1
#@ Project Overview
Our application, Campus Seekr, is designed to allow users around a college campus (Central Michigan Unversity's for our purposes) to report on items lost and/or found around campus with the ultimate goal of reuniting orphaned items to their rightful owners. Our userbase will consist of anyone who frequents the campus and has an interest in ensuring that items that get misplaced around campus will be returned to those to whom they belong. 

When a user loses an item, they will be able to upload relevant information to the app that may assist in locating it, such as a description of the item and its last seen location. When a user locates an item around campus, a user will be able to upload a picture of the item as well as the location it was found at. Users will be able to declare a match between an item that has been reported as lost and an item that has been reported as found.

|Service Category|Relevant Application Features|Our Proposed Vendor|
|----------------|-----------------------------|---------------|
|Object Storage|Store item photographs.|S3 API|
|Relational Data|Storing users, items, and matches.|PostgreSQL|
|Message Broker|Queue photograph processing and lost/found comparisons.|AMQP 0-9-1|
|Metrics|Expose request counts and duration, completed jobs, and processing failures.| Prometheus Exposition|

# Part 2
**API Endpoint Documentation**

Note: Staff has access to all endpoints listed. When staff is stated explicitly it menas staff only

## Items

### GET /api/v1/items/{item_id}
- Description: Get 1 item by ID. 
- Access: Public
- Parameters: item_id: integer
- Response: 200 OK
- Error(s): 404 Not Found

### GET /api/v1/items
- Description: Get all items (paginated, accepts filters). Default sort it `created_at` descending
- Access: Public
- Parameters: page_size: int (max of 100 items returnable, error otherwise); page_num: int (filter parameters: 0|1 \[lost|found\], array of allowed item statuses, location by id, sort type)
- Response: 200 OK
- Error(s): 422 if field is missing or invalid

### GET /api/v1/items/{item_id}/matches
- Description: Get match by item. 
- Access: Public
- Parameters: item_id: integer
- Response: 200 OK
- Error(s): 404 Not Found

### POST /api/v1/items
- Description: Upload an item to the application. 
- Access: Public
- Parameters: name: str, type: int, location_id: int, description: str|None
- Behavior: Status is created as 'open' and created_at is set automatically
- Response: 201 Created and returns item
- Error(s): 422 if missing or incorrect field and data about error; 409 Conflict for duplicates; 404 if location_id doesnt exist

### PATCH /api/v1/items/{item_id}
- Description: Edit an existing item. 
- Access: Owner (only item uploader can edit their item)
- Parameters: id: integer; name, description, location_id can all be updated by Owners, status can be changed to withdrawn; only Staff can change type or status otherwise
- Response: 200 OK and the updated item
- Error(s): 422 if malformed; 404 Not Found if id is wrong

### DELETE /api/v1/items/{item_id}
- Description: Mark an item that is not paired with a match as 'withdrawn'. Does not truly delete
- Access: Owner
- Parameters: id: integer
- Response: 204 No content
- Error(s): 409 if item is part of a match (make this explicitly clear); return 204 if not found

## Matches
### GET /api/v1/matches/{match_id}
- Description: Get 1 match by match_id as well as the item IDs involved in the match. 
- Access: Public
- Parameters: match_id: integer
- Response: 200 OK
- Error(s): 404 Not Found

### POST /api/v1/matches
- Description: Create a match between two items. 
- Access: Owner (only uploaders of 'lost' items can declare matches between items)
- Parameters: lost__item_id: int, found_item_id:int
- Response: 201 Created and the match item
- Error(s): 404 Not Found for incorrect ids, 422 if ids dont match to items correctly, 409 Conflict if items are already in matches or if status is not open

### DELETE /api/v1/matches/{match_id}
- Description: Remove a match and mark both items as open. 
- Access: Owner (only item uploaders can remove their matches)
- Parameters: match_id: integer
- Behavior: Status reset is done in Python. 
- Response: 204 No content
- Error(s): None, return 204 if not found


## Items
### GET /api/v1/locations/{location_id}
- Description: Get 1 location by location_id. 
- Access: Public
- Parameters: location_id: integer
- Response: 200 OK
- Error(s): 404 Not Found

### POST /api/v1/locations
- Description: Create a location. 
- Access: Staff
- Parameters: name: str, coordinates: str, description: str
- Behavior: Auto-set is_active to true
- Response: 201 Created
- Error(s): 409 Conflict if duplicate; 422 if required field missing

### DELETE /api/v1/locations/{location_id}
- Description: Mark location is_active as false. 
- Access: Staff
- Parameters: location_id: integer
- Response: 204 No content
- Error(s): None, return 204 if not found

# Part 3
## Pydantic Schema ("Data Models")
```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class ItemCreate(RequestModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=2000)
    type: Literal[0, 1]  # 0 = lost, 1 = found
    location_id: int = Field(gt=0)

class ItemUpdate(RequestModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, min_length=1, max_length=2000)
    location_id: int | None = Field(None, gt=0)

class ItemOut(ItemCreate):
    model_config = ConfigDict(from_attributes=True)


    id: int = Field(gt=0)
    status: Literal["open", "matched", "returned", "withdrawn", "expired"]
    created_at: datetime

class MatchCreate(RequestModel):
    lost_item_id: int = Field(gt=0)
    found_item_id: int = Field(gt=0)

class MatchUpdate(RequestModel):
    lost_item_id: int | None = Field(None, gt=0)
    found_item_id: int | None = Field(None, gt=0)

class MatchOut(MatchCreate):
    model_config = ConfigDict(from_attributes=True)


    id: int = Field(gt=0)
    created_at: datetime

class LocationCreate(RequestModel):
    name: str = Field(min_length=1, max_length=100)
    coordinates: str = Field(min_length=3, max_length=50)
    description: str = Field(default="", max_length=1000)

class LocationUpdate(RequestModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    coordinates: str | None = Field(None, min_length=3, max_length=50)
    description: str | None = Field(None, max_length=1000)

class LocationOut(LocationCreate):
    model_config = ConfigDict(from_attributes=True)


    id: int = Field(gt=0)
```


# Part 4
## Resource Description
* Item  
  * Item is what the whole application is designed around. It is either something someone lost and posted, or something someone found and posted  
    * If somebody lost something, there doesn't need to be a full "found" post as well, and vice versa. That could be the case, but more likely someone files a "claim" which automatically generates a new item entry, and then a match  
    * Attributes  
      * id (the item id; integer)  
      * name (what the item is called; string) \[could implement specific types later, like 'keys', 'phone', 'other'\]  
      * description (description of the item and details about it; string)  
      * type (lost '0' or found '1'; integer) \[constrained to 0 or 1\]  
      * status (where the item is in its life; string) \[constrained to 'open', 'matched', 'returned', 'withdrawn', or 'expired'; defaults to 'open'\]  
      * location\_id (foreign key; integer)  
      * user\_id (to be implemented later; would be foreign key integer)  
      * tags (to be implemented later; JSON type or array) \[this would enhance matching functionality for users\]  
      * created\_at (date the item was posted; Date type)  
    * Deletion Behavior  
      * Restrict deletions when a match exists. A match means an item got paired with another item, so deleting one side shouldn't erase the other side  
      * "Deleting" a post should normally just set the status to 'withdrawn' and hide it from search. Real deletion is for admin cleanup and spam.  
      * Because the rule is a foreign key constraint, the database enforces it instead of just code. The API can still check for matches first just to give a nicer error than a 500\.  
  * Match  
    * A match is for when someone who lost an item gets matched with someone who found one.  
    * Matches is its own database table, with a match ID, and then 2 item ids (one lost and one found)  
    * Attributes  
      * id (the match id; integer)  
      * lost\_item\_id (foreign key; integer) \[must point at a type '0' item\]  
      * found\_item\_id (foreign key; integer) \[must point at a type '1' item\]  
      * created\_at (date of the match; Date type)  
    * Constraints  
      * The same two items can't be matched twice, and an item can't match itself.  
      * Whether each id points at the right type has to be checked by whatever creates the match, since the database can't check across rows.  
    * Deletion Behavior  
      * Matches can be deleted freely. Deleting a match doesn't touch either item, it just means the two are no longer paired.  
      * Deleting a match should put both items back to 'open', and that needs to be enforced in python  
  * Location  
    * Location is literally a location  
    * I.e. the School of Music; Pearce Hall; Dine and Connect  
    * Each can have some optional data about it, but a location name and coordinate are whats required.  
    * Attributes  
      * id (the location id; integer)  
      * name (name of the location; string)  
      * coordinates (the coordinates of the location; string)  
      * description (optional data about the location; string)  
      * is\_active (whether the location still shows up when posting; boolean)  
    * Deletion Behavior  
      * Restrict deletions when the items exist. Locations will rarely just 'disappear', and we don't want to delete orphan items just because of the location not existing.  
      * Buildings *can* get renamed or closed, so we can retire a location by setting is\_active to false. Old posts can keep using it, but new posts cant

## Data Models
```python
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
    true,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base

# ENUMS # TODO: Move to more relevant file later
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
        "Item", foreign_keys=[lost_item_id], back_populates="lost_matches"
    )
    found_item = relationship(
        "Item", foreign_keys=[found_item_id], back_populates="found_matches"
    )
```

# Part 5
## Error Contract
We will map all errors to this Json format:

{
  "error": {
    "code": "ITEM_NOT_FOUND",
    "detail": "The requested item could not be found."
  }
}
error: Holds all the information about the error.
code: Our error identifier, such as ITEM_NOT_FOUND or VALIDATION_ERROR. The frontend can use it to decide what to show or do.
detail: A readable message for ordinary errors, or a list of problems for validation errors.
We will use a shared exception handler for FastAPI’s 422 errors


200 OK: An item, match, or location was retrieved or updated
201 Created: An item, match, or location was created.
204 No Content: An item was withdrawn, a match was deleted, or a location was retired.
401 Unauthorized: Someone did not sign in.
403 Forbidden: A signed-in user tries to do an admin action.
404 Not Found: The requested item, match, or location does not exist.
422 Unprocessable Entity: The request contains invalid data, such as an empty name or item type
500 Internal Server Error: An unexpected error and the request fails.
503 Service Unavailable: The database cannot be reached.

If the database is unreachable, we return 503. Unexpected application errors return 500

LocationOut leaves out is_active because it is only used internally to decide whether a location can be selected for new posts. Older posts can still show that location after it is retired.

Error messages should explain what went wrong without exposing debugging output, database queries, internal server names, or whether someone’s email is linked to an account.