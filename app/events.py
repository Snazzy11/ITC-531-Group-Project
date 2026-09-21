from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ItemPayload(Payload):
    item_id: int = Field(gt=0, strict=True)


class PotentialMatchPayload(Payload):
    lost_item_id: int = Field(gt=0, strict=True)
    found_item_id: int = Field(gt=0, strict=True)
    score: float = Field(ge=0, le=1, allow_inf_nan=False)


class ConfirmedMatchPayload(Payload):
    match_id: int = Field(gt=0, strict=True)
    lost_item_id: int = Field(gt=0, strict=True)
    found_item_id: int = Field(gt=0, strict=True)


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_id: UUID = Field(default_factory=uuid4)
    schema_version: Literal[1] = 1
    timestamp: AwareDatetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    source: str = Field(min_length=1)


class ItemCreatedEvent(Event):
    event_type: Literal["item.created"] = "item.created"
    payload: ItemPayload


class ItemUpdatedEvent(Event):
    event_type: Literal["item.updated"] = "item.updated"
    payload: ItemPayload


class ItemWithdrawnEvent(Event):
    event_type: Literal["item.withdrawn"] = "item.withdrawn"
    payload: ItemPayload


class PotentialMatchEvent(Event):
    event_type: Literal["match.potential_found"] = "match.potential_found"
    payload: PotentialMatchPayload


class ConfirmedMatchEvent(Event):
    event_type: Literal["match.confirmed"] = "match.confirmed"
    payload: ConfirmedMatchPayload


EVENT_SCHEMAS = {
    "item.created": ItemCreatedEvent,
    "item.updated": ItemUpdatedEvent,
    "item.withdrawn": ItemWithdrawnEvent,
    "match.potential_found": PotentialMatchEvent,
    "match.confirmed": ConfirmedMatchEvent,
}


def build_event(event_type: str, payload: dict, source: str) -> Event:
    if not isinstance(event_type, str) or event_type not in EVENT_SCHEMAS:
        raise ValueError(f"Unsupported event type: {event_type}")
    return EVENT_SCHEMAS[event_type](payload=payload, source=source)
