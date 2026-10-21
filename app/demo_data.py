"""Demo data for an empty database: three users, three locations, and ten
items, two of which (a lost and a found water bottle) are matched. One matching
job is queued, for the lost black backpack.

The app runs this at startup when DEMO_USER_PASSWORD is set, and every demo
user signs in with that password. The admin still comes from
ADMIN_DISPLAY_NAME and ADMIN_PASSWORD (crud.seed_auth). Everything goes through
crud and schemas, so the demo data obeys the same rules as the API.
"""

import logging
from typing import Final, Literal

import crud
import messaging
import schemas
from database import models
from sqlalchemy import select
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

LOST: Final = 0
FOUND: Final = 1

# (display_name, real_name)
USERS = [
    ("alex-rivera", "Alex Rivera"),
    ("jordan-lee", "Jordan Lee"),
    ("sam-patel", "Sam Patel"),
]

# (name, coordinates, description)
LOCATIONS = [
    ("Main Library", "40.1901,-84.2412", "Study floors, printers, and the front desk"),
    ("Student Union", "40.1885,-84.2398", "Food court, bookstore, and lounges"),
    ("Recreation Center", "40.1872,-84.2431", "Gym floor, locker rooms, and the front desk"),
]

# (name, type, location, poster, description)
ITEMS: list[tuple[str, Literal[0, 1], str, str, str]] = [
    (
        "Black backpack", LOST, "Main Library", "jordan-lee",
        (
            "Black backpack with a laptop sleeve and a red keychain on the "
            "zipper, left at a study table on the second floor."
        ),
    ),
    (
        "Black backpack", FOUND, "Student Union", "sam-patel",
        (
            "Found a black backpack with a red keychain on the zipper under a "
            "table near the food court."
        ),
    ),
    (
        "Silver water bottle", LOST, "Recreation Center", "alex-rivera",
        (
            "Silver metal water bottle with a dented bottom and a mountain "
            "sticker on the side, left by the treadmills."
        ),
    ),
    (
        "Water bottle", FOUND, "Recreation Center", "jordan-lee",
        (
            "Silver metal water bottle with a mountain sticker on the side, "
            "found next to the treadmills after the evening rush."
        ),
    ),
    (
        "Student ID card", LOST, "Main Library", "sam-patel",
        (
            "Student ID card in a clear plastic holder on a blue lanyard, "
            "probably dropped near the printers on the first floor."
        ),
    ),
    (
        "Blue lanyard", FOUND, "Main Library", "alex-rivera",
        (
            "Blue lanyard with a clear card holder, found next to the printers "
            "on the first floor. The card holder was empty."
        ),
    ),
    (
        "Wireless earbuds", LOST, "Student Union", "jordan-lee",
        (
            "White wireless earbuds in a small charging case, lost somewhere "
            "between the bookstore and the coffee shop."
        ),
    ),
    (
        "Car keys", FOUND, "Recreation Center", "sam-patel",
        (
            "Set of car keys with a black fob and a small brass key, found in "
            "the locker room near the front desk."
        ),
    ),
    (
        "Grey hoodie", LOST, "Student Union", "alex-rivera",
        (
            "Grey zip-up hoodie with the university logo on the front and a "
            "small hole in the left cuff, left on a chair in the lounge."
        ),
    ),
    (
        "Umbrella", FOUND, "Main Library", "jordan-lee",
        (
            "Navy blue compact umbrella with a wooden handle, found in the "
            "umbrella stand by the main entrance."
        ),
    ),
]

# Positions in ITEMS of the lost and the found item that are matched.
MATCHED_PAIR = (2, 3)


def seed(db: Session, password: str) -> bool:
    """Adds the demo data and returns True. Returns False without changing
    anything if a location already exists, since then the database isn't new.
    A password the API would refuse raises before anything is written."""
    if db.scalar(select(models.Location.id).limit(1)) is not None:
        return False

    new_users = [
        schemas.UserCreate(display_name=name, real_name=real_name, password=password)
        for name, real_name in USERS
    ]
    users = {}
    for new_user in new_users:
        # Reused if they survived a wipe of every location and item
        existing = db.scalar(
            select(models.User).where(models.User.display_name == new_user.display_name)
        )
        users[new_user.display_name] = existing or crud.create_user(db, new_user)

    locations = {
        name: crud.create_location(
            db,
            schemas.LocationCreate(
                name=name, coordinates=coordinates, description=description
            ),
        )
        for name, coordinates, description in LOCATIONS
    }

    items = [
        crud.create_item(
            db,
            schemas.ItemCreate(
                name=name,
                type=item_type,
                location_id=locations[location].id,
                description=description,
            ),
            user_id=users[poster].id,
        )
        for name, item_type, location, poster, description in ITEMS
    ]
    lost, found = (items[i] for i in MATCHED_PAIR)
    crud.create_match(db, lost, found)
    # One matching job, so a fresh start has suggestions to show: the lost
    # backpack has a look-alike found backpack. The rest can be run on demand
    # with POST /items/{id}/match-search.
    messaging.queue_matching(items[0].id)

    log.info(
        "seeded demo data: %d users, %d locations, %d items, 1 match",
        len(users), len(locations), len(items),
    )
    return True
