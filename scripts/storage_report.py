"""Storage report. Lists every object in the bucket and checks it against our
key scheme, the upload-id stamp, and the database.

Based on Parker's homework Part 3 script (same unstamped, off-scheme and
bytes-by-prefix checks and exit codes), changed to use our storage port and key
scheme, and with an extra check against the database.

Run it inside the app container so it has the same env as the app:

    docker compose --env-file .env.local exec -T app python - < scripts/storage_report.py
    docker compose --env-file .env.local exec -T app python - --prefix users/ < scripts/storage_report.py

Exit codes: 0 = clean, 1 = found issue, 2 = couldn't run due to error
"""

import argparse
import re
import sys

from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.exc import SQLAlchemyError

from database.database import SessionLocal
from database.models import File, Image, ImageStatus
from ports import storage

UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}" # UUID regex
SCHEME = re.compile( # strings are "raw" for regex
    rf"uploads/pending/{UUID}"
    rf"|items/\d+/{UUID}/photo\.jpg"
    rf"|users/\d+/files/{UUID}\.(jpg|png|webp|heic|pdf)"
)


def index(db) -> tuple[set[str], set[str]]:
    """Returns the keys the database says should exist, and the pending keys
    that might exist (an upload link that hasn't been used yet has a row but no
    object yet)."""
    required = {key for (key,) in db.query(File.key)}
    required |= {
        key
        for (key,) in db.query(Image.photo_key).filter(Image.status == ImageStatus.READY)
    }
    in_flight = {
        storage.pending_key(upload_id)
        for (upload_id,) in db.query(Image.upload_id).filter(
            Image.status.in_([ImageStatus.AWAITING_UPLOAD, ImageStatus.PROCESSING])
        )
    }
    return required, in_flight


def section(title: str, keys: list[str]) -> None:
    print(f"\n{title}: {len(keys)}")
    for key in keys:
        print(f"  {key}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default="")
    args = parser.parse_args()

    try:
        objects = dict(storage.list_objects(args.prefix))
        unstamped = []
        for key in objects:
            stamp = storage.metadata(key)
            if stamp is None or storage.STAMP not in stamp:
                unstamped.append(key)
        with SessionLocal() as db:
            required, in_flight = index(db)
    except (BotoCoreError, ClientError, SQLAlchemyError, KeyError) as exc:
        print(f"ERROR: could not run report: {exc!r}", file=sys.stderr)
        return 2

    off_scheme = [key for key in objects if not SCHEME.fullmatch(key)]
    no_row = [key for key in objects if key not in required | in_flight]
    no_object = sorted(
        key for key in required if key.startswith(args.prefix) and key not in objects
    )

    totals: dict[str, int] = {}
    for key, size in objects.items():
        top = key.split("/")[0]
        totals[top] = totals.get(top, 0) + size

    print(
        f"Storage report: bucket={storage.bucket_name()} prefix={args.prefix!r} "
        f"objects={len(objects)} indexed={len(required)} in_flight={len(in_flight)}"
    )
    section("Unstamped objects (no upload-id)", unstamped)
    section("Off-scheme keys", off_scheme)
    section("Objects with no row", no_row)
    section("Rows with no object", no_object)
    print("\nBytes by top-level prefix:")
    for top in sorted(totals):
        print(f"  {top}: {totals[top]}")
    print(f"  TOTAL: {sum(totals.values())}")

    return 1 if unstamped or off_scheme or no_row or no_object else 0


if __name__ == "__main__":
    sys.exit(main())
